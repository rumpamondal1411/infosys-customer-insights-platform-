"""
Milestone 2 — Module 4: Customer Behaviour & Recommendation Analytics.

Builds on Transaction (purchase history) and ProductView (browsing/
engagement signal) to deliver:
  - Customer purchase-history / browsing-behaviour / engagement profiling.
  - Customer segmentation via KMeans clustering on RFM + engagement
    features (Recency, Frequency, Monetary, Views).
  - Personalized product recommendations via item-based collaborative
    filtering (cosine similarity over a customer x product purchase
    matrix) and content-based filtering (category affinity), with a
    popularity-based fallback for cold-start customers.
  - Churn-risk scoring from purchase recency/frequency trends.

All heavy lifting is pandas/scikit-learn based, mirroring the pattern
already used in analytics_service.py and revenue_intelligence_service.py.
"""
from datetime import datetime
from typing import Optional

import numpy as np
import pandas as pd
from sqlalchemy.orm import Session

from app.models.customer import Customer
from app.models.transaction import Transaction, TransactionStatus
from app.models.product import Product, ProductStatus
from app.models.product_view import ProductView
from app.models.category import Category

MIN_CUSTOMERS_FOR_CLUSTERING = 4


# ------------------------------------------------------------------ Data

def _purchases_df(db: Session) -> pd.DataFrame:
    rows = (
        db.query(
            Transaction.customer_id,
            Transaction.product_id,
            Transaction.quantity,
            Transaction.total_amount,
            Transaction.transaction_date,
            Product.category_id,
            Product.name.label("product_name"),
        )
        .join(Product, Transaction.product_id == Product.id)
        .filter(Transaction.status == TransactionStatus.COMPLETED)
        .filter(Transaction.customer_id.isnot(None))
        .all()
    )
    cols = ["customer_id", "product_id", "quantity", "total_amount",
            "transaction_date", "category_id", "product_name"]
    if not rows:
        return pd.DataFrame(columns=cols)
    df = pd.DataFrame(rows, columns=cols)
    df["transaction_date"] = pd.to_datetime(df["transaction_date"])
    return df


def _views_df(db: Session) -> pd.DataFrame:
    rows = (
        db.query(
            ProductView.customer_id,
            ProductView.product_id,
            ProductView.viewed_at,
            Product.category_id,
        )
        .join(Product, ProductView.product_id == Product.id)
        .all()
    )
    cols = ["customer_id", "product_id", "viewed_at", "category_id"]
    if not rows:
        return pd.DataFrame(columns=cols)
    df = pd.DataFrame(rows, columns=cols)
    df["viewed_at"] = pd.to_datetime(df["viewed_at"])
    return df


# ---------------------------------------------------------- RFM features

def _rfm_features(db: Session) -> pd.DataFrame:
    """One row per customer with Recency/Frequency/Monetary + engagement."""
    customers = db.query(Customer.id, Customer.name, Customer.email).all()
    if not customers:
        return pd.DataFrame(columns=[
            "customer_id", "name", "email", "recency_days", "frequency",
            "monetary", "avg_order_value", "views", "distinct_categories",
        ])

    purchases = _purchases_df(db)
    views = _views_df(db)
    now = purchases["transaction_date"].max() if not purchases.empty else pd.Timestamp(datetime.utcnow())
    if pd.isna(now):
        now = pd.Timestamp(datetime.utcnow())

    records = []
    for cid, name, email in customers:
        cust_purchases = purchases[purchases["customer_id"] == cid]
        cust_views = views[views["customer_id"] == cid] if not views.empty else views

        frequency = int(cust_purchases.shape[0])
        monetary = round(float(cust_purchases["total_amount"].sum()), 2) if frequency else 0.0
        avg_order_value = round(monetary / frequency, 2) if frequency else 0.0

        if frequency:
            last_purchase = cust_purchases["transaction_date"].max()
            recency_days = float((now - last_purchase).days)
        else:
            recency_days = 9999.0  # never purchased -> maximally "stale"

        views_count = int(cust_views.shape[0]) if not cust_views.empty else 0
        distinct_categories = int(cust_purchases["category_id"].nunique()) if frequency else 0

        records.append({
            "customer_id": cid,
            "name": name,
            "email": email,
            "recency_days": recency_days,
            "frequency": frequency,
            "monetary": monetary,
            "avg_order_value": avg_order_value,
            "views": views_count,
            "distinct_categories": distinct_categories,
        })

    return pd.DataFrame(records)


# ------------------------------------------------------------ Profiling

def customer_profile(db: Session, customer_id: int) -> dict:
    """Purchase history + browsing behaviour + engagement for one customer."""
    customer = db.query(Customer).filter(Customer.id == customer_id).first()
    if not customer:
        return {}

    purchases = _purchases_df(db)
    views = _views_df(db)
    cust_purchases = purchases[purchases["customer_id"] == customer_id]
    cust_views = views[views["customer_id"] == customer_id] if not views.empty else views

    favorite_category_id = None
    if not cust_purchases.empty:
        cat_totals = cust_purchases.dropna(subset=["category_id"]).groupby("category_id")["quantity"].sum()
        if not cat_totals.empty:
            favorite_category_id = int(cat_totals.idxmax())
    category_name = None
    if favorite_category_id is not None:
        cat = db.query(Category).filter(Category.id == favorite_category_id).first()
        category_name = cat.name if cat else None

    rfm = _rfm_features(db)
    row = rfm[rfm["customer_id"] == customer_id]
    segment_label = None
    if not row.empty:
        segments = segment_customers(db)
        seg_row = next((s for s in segments["customers"] if s["customer_id"] == customer_id), None)
        segment_label = seg_row["segment"] if seg_row else None

    return {
        "customer_id": customer.id,
        "name": customer.name,
        "email": customer.email,
        "total_orders": int(cust_purchases.shape[0]),
        "total_spent": round(float(cust_purchases["total_amount"].sum()), 2) if not cust_purchases.empty else 0.0,
        "total_products_viewed": int(cust_views.shape[0]) if not cust_views.empty else 0,
        "favorite_category": category_name,
        "recent_purchases": (
            cust_purchases.sort_values("transaction_date", ascending=False)
            .head(10)[["product_id", "product_name", "quantity", "total_amount", "transaction_date"]]
            .assign(transaction_date=lambda d: d["transaction_date"].dt.strftime("%Y-%m-%d %H:%M"))
            .to_dict(orient="records")
        ),
        "segment": segment_label,
    }


def customer_revenue_analysis(db: Session, customer_id: int) -> dict:
    """
    Customer-facing revenue analysis — 'how much have I spent, on what, and
    when'. Mirrors the shape of the admin-facing revenue intelligence /
    marketplace benchmarking reports (Milestone 3), scoped to a single
    customer so it can power a "My Spending" view on the customer dashboard.
    """
    customer = db.query(Customer).filter(Customer.id == customer_id).first()
    if not customer:
        return {}

    purchases = _purchases_df(db)
    cust_purchases = purchases[purchases["customer_id"] == customer_id].copy()

    if cust_purchases.empty:
        return {
            "customer_id": customer.id,
            "total_spent": 0.0,
            "total_orders": 0,
            "avg_order_value": 0.0,
            "monthly_trend": [],
            "category_breakdown": [],
        }

    total_spent = round(float(cust_purchases["total_amount"].sum()), 2)
    total_orders = int(cust_purchases.shape[0])
    avg_order_value = round(total_spent / total_orders, 2) if total_orders else 0.0

    monthly = (
        cust_purchases.set_index("transaction_date")
        .resample("ME")
        .agg(revenue=("total_amount", "sum"), orders=("product_id", "count"))
        .reset_index()
    )
    monthly = monthly[monthly["orders"] > 0]
    monthly["revenue"] = monthly["revenue"].round(2)
    monthly["month"] = monthly["transaction_date"].dt.strftime("%Y-%m")
    monthly_trend = monthly[["month", "revenue", "orders"]].to_dict(orient="records")

    cat_ids = cust_purchases["category_id"].dropna().unique().tolist()
    categories = (
        {c.id: c.name for c in db.query(Category).filter(Category.id.in_(cat_ids)).all()}
        if cat_ids else {}
    )

    cat_grouped = (
        cust_purchases.dropna(subset=["category_id"])
        .groupby("category_id")
        .agg(revenue=("total_amount", "sum"), units=("quantity", "sum"))
        .reset_index()
        .sort_values("revenue", ascending=False)
    )
    cat_grouped["revenue"] = cat_grouped["revenue"].round(2)
    category_breakdown = [
        {
            "category_id": int(row["category_id"]),
            "category_name": categories.get(int(row["category_id"]), "Unknown"),
            "revenue": float(row["revenue"]),
            "units": int(row["units"]),
        }
        for _, row in cat_grouped.iterrows()
    ]

    return {
        "customer_id": customer.id,
        "total_spent": total_spent,
        "total_orders": total_orders,
        "avg_order_value": avg_order_value,
        "monthly_trend": monthly_trend,
        "category_breakdown": category_breakdown,
    }


# --------------------------------------------------------- Segmentation

def _label_segments(cluster_summary: pd.DataFrame) -> dict:
    """
    Assigns human-readable labels to cluster ids based on their mean RFM
    profile, so the label is meaningful regardless of how sklearn ordered
    the clusters this run.
    """
    labels = {}
    ranked_by_value = cluster_summary.sort_values(
        by=["monetary", "frequency"], ascending=False
    ).index.tolist()

    for rank, cluster_id in enumerate(ranked_by_value):
        row = cluster_summary.loc[cluster_id]
        if row["frequency"] == 0:
            labels[cluster_id] = "Browsers (No Purchases Yet)"
        elif row["recency_days"] > 45 and row["frequency"] <= cluster_summary["frequency"].median():
            labels[cluster_id] = "At Risk"
        elif rank == 0:
            labels[cluster_id] = "Champions"
        elif rank == len(ranked_by_value) - 1:
            labels[cluster_id] = "Low Engagement"
        else:
            labels[cluster_id] = "Loyal Customers"
    return labels


def segment_customers(db: Session, n_clusters: int = 4) -> dict:
    """
    Customer segmentation via KMeans clustering on standardized RFM +
    engagement features (Recency, Frequency, Monetary, Views).
    Falls back to a simple rule-based split when there aren't enough
    customers for meaningful clustering.
    """
    rfm = _rfm_features(db)
    if rfm.empty:
        return {"clusters": [], "customers": [], "n_clusters": 0}

    feature_cols = ["recency_days", "frequency", "monetary", "views"]
    X = rfm[feature_cols].copy()
    # Cap recency so a customer who never purchased doesn't blow up scaling
    X["recency_days"] = X["recency_days"].clip(upper=365)

    if rfm.shape[0] < MIN_CUSTOMERS_FOR_CLUSTERING:
        # Not enough data for KMeans to be meaningful — simple rule-based split
        def rule_label(r):
            if r["frequency"] == 0:
                return "Browsers (No Purchases Yet)"
            if r["recency_days"] > 45:
                return "At Risk"
            return "Loyal Customers"
        rfm["segment"] = rfm.apply(rule_label, axis=1)
        rfm["cluster_id"] = rfm["segment"].astype("category").cat.codes
    else:
        from sklearn.preprocessing import StandardScaler
        from sklearn.cluster import KMeans

        scaler = StandardScaler()
        X_scaled = scaler.fit_transform(X)

        k = min(n_clusters, rfm.shape[0])
        kmeans = KMeans(n_clusters=k, random_state=42, n_init=10)
        rfm["cluster_id"] = kmeans.fit_predict(X_scaled)

        cluster_summary = rfm.groupby("cluster_id")[feature_cols].mean()
        labels = _label_segments(cluster_summary)
        rfm["segment"] = rfm["cluster_id"].map(labels)

    cluster_summary = (
        rfm.groupby("segment")
        .agg(
            customer_count=("customer_id", "count"),
            avg_recency_days=("recency_days", "mean"),
            avg_frequency=("frequency", "mean"),
            avg_monetary=("monetary", "mean"),
            avg_views=("views", "mean"),
        )
        .reset_index()
    )
    for col in ("avg_recency_days", "avg_frequency", "avg_monetary", "avg_views"):
        cluster_summary[col] = cluster_summary[col].round(2)
    cluster_summary = cluster_summary.sort_values("avg_monetary", ascending=False)

    customers_out = rfm[[
        "customer_id", "name", "email", "segment", "recency_days",
        "frequency", "monetary", "avg_order_value", "views",
    ]].round({"recency_days": 1, "monetary": 2, "avg_order_value": 2}).to_dict(orient="records")

    return {
        "clusters": cluster_summary.to_dict(orient="records"),
        "customers": customers_out,
        "n_clusters": int(rfm["segment"].nunique()),
    }


# ------------------------------------------------------- Recommendations

def _popular_products(db: Session, top_n: int = 10) -> list[dict]:
    """Fallback for cold-start customers: best sellers overall."""
    purchases = _purchases_df(db)
    if purchases.empty:
        return []
    popularity = (
        purchases.groupby(["product_id", "product_name"])
        .agg(units_sold=("quantity", "sum"), revenue=("total_amount", "sum"))
        .reset_index()
        .sort_values(["units_sold", "revenue"], ascending=False)
        .head(top_n)
    )
    popularity["revenue"] = popularity["revenue"].round(2)
    popularity["reason"] = "Popular with other customers"
    return popularity.to_dict(orient="records")


def _collaborative_filtering(db: Session, customer_id: int, purchases: pd.DataFrame, top_n: int) -> pd.DataFrame:
    """
    Item-based collaborative filtering: build a customer x product matrix
    of quantities purchased, compute item-item cosine similarity, then
    score candidate products by their similarity to items this customer
    already bought (weighted by how much they bought of each).
    """
    from sklearn.metrics.pairwise import cosine_similarity

    matrix = purchases.pivot_table(
        index="customer_id", columns="product_id", values="quantity", aggfunc="sum", fill_value=0
    )
    if customer_id not in matrix.index or matrix.shape[1] < 2 or matrix.shape[0] < 2:
        return pd.DataFrame(columns=["product_id", "score"])

    item_similarity = cosine_similarity(matrix.T.values)
    product_ids = matrix.columns.tolist()
    sim_df = pd.DataFrame(item_similarity, index=product_ids, columns=product_ids)

    customer_vector = matrix.loc[customer_id]
    purchased_products = customer_vector[customer_vector > 0].index.tolist()
    if not purchased_products:
        return pd.DataFrame(columns=["product_id", "score"])

    scores = sim_df[purchased_products].mul(customer_vector[purchased_products], axis=1).sum(axis=1)
    scores = scores.drop(labels=purchased_products, errors="ignore")
    scores = scores.sort_values(ascending=False).head(top_n)

    return pd.DataFrame({"product_id": scores.index, "score": scores.values})


def _content_based(db: Session, customer_id: int, purchases: pd.DataFrame, views: pd.DataFrame, top_n: int) -> pd.DataFrame:
    """
    Content-based filtering: recommend popular active products from the
    categories this customer has purchased from or browsed most, that
    they haven't already bought.
    """
    cust_purchases = purchases[purchases["customer_id"] == customer_id]
    cust_views = views[views["customer_id"] == customer_id] if not views.empty else views

    category_ids = set(cust_purchases["category_id"].dropna().astype(int).tolist())
    if not cust_views.empty:
        category_ids |= set(cust_views["category_id"].dropna().astype(int).tolist())

    if not category_ids:
        return pd.DataFrame(columns=["product_id", "score"])

    already_bought = set(cust_purchases["product_id"].tolist())

    candidates = (
        db.query(Product.id, Product.category_id)
        .filter(Product.category_id.in_(category_ids))
        .filter(Product.status == ProductStatus.ACTIVE)
        .all()
    )
    candidate_ids = [p.id for p in candidates if p.id not in already_bought]
    if not candidate_ids:
        return pd.DataFrame(columns=["product_id", "score"])

    # Score by overall popularity within the matching categories
    popularity = (
        purchases[purchases["product_id"].isin(candidate_ids)]
        .groupby("product_id")["quantity"].sum()
    )
    scored = pd.DataFrame({"product_id": candidate_ids})
    scored["score"] = scored["product_id"].map(popularity).fillna(0.0)
    scored = scored.sort_values("score", ascending=False).head(top_n)
    return scored


def recommend_for_customer(db: Session, customer_id: int, top_n: int = 8) -> dict:
    """
    Personalized product recommendations combining collaborative
    filtering and content-based filtering, with a popularity fallback
    for customers with no purchase history yet (cold start).
    """
    purchases = _purchases_df(db)
    views = _views_df(db)

    collab = _collaborative_filtering(db, customer_id, purchases, top_n) if not purchases.empty else pd.DataFrame(columns=["product_id", "score"])
    content = _content_based(db, customer_id, purchases, views, top_n) if not purchases.empty else pd.DataFrame(columns=["product_id", "score"])

    combined_ids: list[tuple[int, str]] = []
    for pid in collab["product_id"].tolist():
        combined_ids.append((int(pid), "Based on your past purchases"))
    for pid in content["product_id"].tolist():
        if pid not in [c[0] for c in combined_ids]:
            combined_ids.append((int(pid), "From categories you shop in"))

    if len(combined_ids) < top_n:
        for row in _popular_products(db, top_n=top_n):
            if row["product_id"] not in [c[0] for c in combined_ids]:
                combined_ids.append((row["product_id"], "Popular with other customers"))
            if len(combined_ids) >= top_n:
                break

    combined_ids = combined_ids[:top_n]
    if not combined_ids:
        return {"customer_id": customer_id, "recommendations": [], "strategy": "none"}

    product_ids = [pid for pid, _ in combined_ids]
    products = db.query(Product).filter(Product.id.in_(product_ids)).all()
    products_by_id = {p.id: p for p in products}

    recommendations = []
    for pid, reason in combined_ids:
        product = products_by_id.get(pid)
        if not product:
            continue
        recommendations.append({
            "product_id": product.id,
            "name": product.name,
            "price": product.price,
            "image_url": product.image_url,
            "vendor_id": product.vendor_id,
            "rating": product.rating,
            "rating_count": product.rating_count,
            "quantity_available": product.quantity_available,
            "reason": reason,
        })

    strategy = "collaborative+content" if not purchases[purchases["customer_id"] == customer_id].empty else "popularity (cold start)"
    return {"customer_id": customer_id, "recommendations": recommendations, "strategy": strategy}


# --------------------------------------------------------------- Churn

def churn_risk(db: Session) -> list[dict]:
    """
    Flags customers at risk of churning based on purchase recency versus
    their own historical buying cadence: a customer who used to buy every
    ~10 days but hasn't ordered in 40 is a much stronger churn signal than
    a customer who has always bought roughly once a quarter.
    """
    purchases = _purchases_df(db)
    customers = db.query(Customer).all()
    if not customers:
        return []

    now = purchases["transaction_date"].max() if not purchases.empty else pd.Timestamp(datetime.utcnow())
    if pd.isna(now):
        now = pd.Timestamp(datetime.utcnow())

    results = []
    for customer in customers:
        cust_purchases = purchases[purchases["customer_id"] == customer.id].sort_values("transaction_date")

        if cust_purchases.shape[0] == 0:
            results.append({
                "customer_id": customer.id, "name": customer.name, "email": customer.email,
                "risk_level": "New / No Purchases", "risk_score": 0.5,
                "days_since_last_purchase": None, "avg_days_between_purchases": None,
                "total_orders": 0,
            })
            continue

        last_purchase = cust_purchases["transaction_date"].max()
        days_since_last = float((now - last_purchase).days)

        if cust_purchases.shape[0] >= 2:
            dates = cust_purchases["transaction_date"].sort_values()
            gaps = dates.diff().dropna().dt.days
            avg_gap = float(gaps.mean()) if len(gaps) else 30.0
        else:
            avg_gap = 30.0  # assume a monthly cadence baseline for single-purchase customers

        avg_gap = max(avg_gap, 1.0)
        # Risk grows once the gap since last purchase exceeds ~2x the customer's
        # own average cadence; scaled into a 0-1 score and capped at 1.0.
        risk_score = round(min(days_since_last / (avg_gap * 2.5), 1.0), 2)

        if risk_score >= 0.75:
            risk_level = "High"
        elif risk_score >= 0.4:
            risk_level = "Medium"
        else:
            risk_level = "Low"

        results.append({
            "customer_id": customer.id, "name": customer.name, "email": customer.email,
            "risk_level": risk_level, "risk_score": risk_score,
            "days_since_last_purchase": int(days_since_last),
            "avg_days_between_purchases": round(avg_gap, 1),
            "total_orders": int(cust_purchases.shape[0]),
        })

    results.sort(key=lambda r: r["risk_score"], reverse=True)
    return results


# --------------------------------------------------------- Dashboard

def customer_analytics_dashboard(db: Session) -> dict:
    """One-call payload for the admin-facing Customer Analytics dashboard."""
    segments = segment_customers(db)
    churn = churn_risk(db)
    total_customers = db.query(Customer).count()

    high_risk = [c for c in churn if c["risk_level"] == "High"]

    return {
        "total_customers": total_customers,
        "segments": segments,
        "churn_risk": churn[:20],
        "high_risk_count": len(high_risk),
    }
