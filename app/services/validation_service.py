"""
Milestone 2 — Step 4: Validate analytical outputs against historical
marketplace performance datasets.

This is the piece the mentor's brief calls for but the reference Node/Mongo
code never actually implements (his notes just state target thresholds:
forecast accuracy >= 80%, segmentation quality >= 85%, recommendation
relevance >= 75%). This service computes each of those three numbers for
real, against this database's actual transaction history — nothing here
is hard-coded or assumed.

  - forecast_accuracy(): backtests the moving-average forecaster. For each
    product with enough history, it "hides" the most recent `horizon_days`
    of sales, forecasts from everything before that using the same method
    as inventory_forecast_service, then compares the forecast to what
    actually sold in the hidden window.
  - segmentation_quality(): silhouette score of the KMeans clustering from
    customer_analytics_service.segment_customers(), which measures how
    well-separated the resulting clusters are (the standard, accepted way
    to score clustering quality when there's no ground-truth label to
    compare against) — normalized to a 0-100% scale for comparison against
    the mentor's threshold.
  - recommendation_relevance(): leave-one-out evaluation. For each customer
    with 2+ completed orders, their most recent order is hidden, the
    recommendation engine is re-run on everything before it, and a hit is
    counted if the hidden purchase (or its category) shows up in the
    resulting recommendations.
"""
import pandas as pd
from sqlalchemy.orm import Session

from app.models.transaction import Transaction, TransactionStatus
from app.models.product import Product
from app.services import customer_analytics_service as ca

FORECAST_ACCURACY_THRESHOLD = 80.0
SEGMENTATION_QUALITY_THRESHOLD = 85.0
RECOMMENDATION_RELEVANCE_THRESHOLD = 75.0

MIN_DAYS_HISTORY_FOR_BACKTEST = 14


# --------------------------------------------------------- Forecast accuracy

def forecast_accuracy(db: Session, horizon_days: int = 7, days_history: int = 30) -> dict:
    """
    Backtests the moving-average forecaster per product: forecast is
    computed using only data *before* the last `horizon_days`, then
    compared against what actually sold in that held-out window.
    """
    rows = (
        db.query(Transaction.product_id, Transaction.quantity, Transaction.transaction_date)
        .filter(Transaction.status == TransactionStatus.COMPLETED)
        .all()
    )
    if not rows:
        return {
            "products_evaluated": 0, "overall_accuracy_pct": 0.0,
            "threshold_pct": FORECAST_ACCURACY_THRESHOLD, "meets_threshold": False,
            "per_product": [],
        }

    df = pd.DataFrame(rows, columns=["product_id", "quantity", "transaction_date"])
    df["transaction_date"] = pd.to_datetime(df["transaction_date"])

    results = []
    for product_id, group in df.groupby("product_id"):
        span_days = (group["transaction_date"].max() - group["transaction_date"].min()).days
        if span_days < MIN_DAYS_HISTORY_FOR_BACKTEST:
            continue  # not enough history to meaningfully hold out a test window

        cutoff = group["transaction_date"].max() - pd.Timedelta(days=horizon_days)
        train = group[group["transaction_date"] < cutoff]
        test = group[group["transaction_date"] >= cutoff]

        if train.empty:
            continue

        train_span = max((train["transaction_date"].max() - train["transaction_date"].min()).days, 1)
        avg_daily = float(train["quantity"].sum()) / train_span
        predicted = round(avg_daily * horizon_days, 2)
        actual = float(test["quantity"].sum())

        if actual == 0 and predicted == 0:
            accuracy_pct = 100.0
        else:
            error_pct = abs(predicted - actual) / max(actual, 1.0)
            accuracy_pct = round(max(0.0, 1.0 - min(error_pct, 1.0)) * 100, 2)

        results.append({
            "product_id": int(product_id),
            "predicted_units": predicted,
            "actual_units": actual,
            "accuracy_pct": accuracy_pct,
        })

    if not results:
        return {
            "products_evaluated": 0, "overall_accuracy_pct": 0.0,
            "threshold_pct": FORECAST_ACCURACY_THRESHOLD, "meets_threshold": False,
            "per_product": [],
            "note": f"No product has >= {MIN_DAYS_HISTORY_FOR_BACKTEST} days of history to backtest yet.",
        }

    overall = round(sum(r["accuracy_pct"] for r in results) / len(results), 2)
    results.sort(key=lambda r: r["accuracy_pct"], reverse=True)

    return {
        "products_evaluated": len(results),
        "overall_accuracy_pct": overall,
        "threshold_pct": FORECAST_ACCURACY_THRESHOLD,
        "meets_threshold": overall >= FORECAST_ACCURACY_THRESHOLD,
        "per_product": results[:25],
    }


# --------------------------------------------------------- Segmentation quality

def segmentation_quality(db: Session, n_clusters: int = 4) -> dict:
    """
    Silhouette score of the customer segmentation clustering — the
    standard metric for judging cluster quality without ground-truth
    labels (how similar each customer is to their own cluster vs. the
    next-nearest one). Scaled to 0-100% for comparison against the
    mentor's stated threshold; a raw silhouette score is also returned
    since the 0-100% framing is an approximation of a [-1, 1] metric.
    """
    rfm = ca._rfm_features(db)
    if rfm.shape[0] < max(ca.MIN_CUSTOMERS_FOR_CLUSTERING, n_clusters + 1):
        return {
            "quality_pct": 0.0, "silhouette_score": None,
            "threshold_pct": SEGMENTATION_QUALITY_THRESHOLD, "meets_threshold": False,
            "customers_evaluated": int(rfm.shape[0]),
            "note": "Not enough customers yet for a meaningful clustering quality score.",
        }

    from sklearn.preprocessing import StandardScaler
    from sklearn.cluster import KMeans
    from sklearn.metrics import silhouette_score

    feature_cols = ["recency_days", "frequency", "monetary", "views"]
    X = rfm[feature_cols].copy()
    X["recency_days"] = X["recency_days"].clip(upper=365)
    X_scaled = StandardScaler().fit_transform(X)

    k = min(n_clusters, rfm.shape[0] - 1)
    labels = KMeans(n_clusters=k, random_state=42, n_init=10).fit_predict(X_scaled)

    if len(set(labels)) < 2:
        return {
            "quality_pct": 0.0, "silhouette_score": None,
            "threshold_pct": SEGMENTATION_QUALITY_THRESHOLD, "meets_threshold": False,
            "customers_evaluated": int(rfm.shape[0]),
            "note": "Clustering collapsed to a single group — customer behaviour is too uniform to score.",
        }

    score = float(silhouette_score(X_scaled, labels))
    quality_pct = round((score + 1) / 2 * 100, 2)  # map [-1, 1] -> [0, 100]

    return {
        "quality_pct": quality_pct,
        "silhouette_score": round(score, 4),
        "threshold_pct": SEGMENTATION_QUALITY_THRESHOLD,
        "meets_threshold": quality_pct >= SEGMENTATION_QUALITY_THRESHOLD,
        "customers_evaluated": int(rfm.shape[0]),
        "n_clusters": k,
    }


# --------------------------------------------------------- Recommendation relevance

def recommendation_relevance(db: Session, top_n: int = 8) -> dict:
    """
    Leave-one-out evaluation: for each customer with 2+ completed orders,
    hide their most recent order, regenerate recommendations from
    everything before it, and count a hit if the hidden product (or its
    category) appears in the resulting recommendation list.
    """
    purchases = ca._purchases_df(db)
    views = ca._views_df(db)

    if purchases.empty:
        return {
            "customers_evaluated": 0, "relevance_pct": 0.0,
            "threshold_pct": RECOMMENDATION_RELEVANCE_THRESHOLD, "meets_threshold": False,
            "note": "No purchase history yet to evaluate recommendations against.",
        }

    evaluated = 0
    exact_hits = 0
    category_hits = 0

    for customer_id, group in purchases.groupby("customer_id"):
        if group.shape[0] < 2:
            continue  # need at least one prior purchase plus one to hold out

        group = group.sort_values("transaction_date")
        held_out = group.iloc[-1]
        train_purchases = purchases[
            ~((purchases["customer_id"] == customer_id) & (purchases.index == held_out.name))
        ]

        collab = ca._collaborative_filtering(db, customer_id, train_purchases, top_n)
        content = ca._content_based(db, customer_id, train_purchases, views, top_n)
        recommended_ids = set(collab["product_id"].tolist()) | set(content["product_id"].tolist())

        if not recommended_ids:
            evaluated += 1
            continue

        evaluated += 1
        if int(held_out["product_id"]) in recommended_ids:
            exact_hits += 1

        held_out_category = held_out["category_id"]
        recommended_categories = set(
            db.query(Product.category_id).filter(Product.id.in_(recommended_ids)).all()
        )
        recommended_categories = {c[0] for c in recommended_categories}
        if pd.notna(held_out_category) and held_out_category in recommended_categories:
            category_hits += 1

    if evaluated == 0:
        return {
            "customers_evaluated": 0, "relevance_pct": 0.0,
            "threshold_pct": RECOMMENDATION_RELEVANCE_THRESHOLD, "meets_threshold": False,
            "note": "No customer has 2+ completed orders yet — need repeat purchases to evaluate against.",
        }

    # A hit on the exact held-out product OR its category both count as
    # "relevant" — an e-commerce recommender that suggests the right
    # category is still useful even if it's not the identical SKU.
    relevant = max(exact_hits, category_hits)
    relevance_pct = round(relevant / evaluated * 100, 2)

    return {
        "customers_evaluated": evaluated,
        "exact_product_hit_rate_pct": round(exact_hits / evaluated * 100, 2),
        "category_hit_rate_pct": round(category_hits / evaluated * 100, 2),
        "relevance_pct": relevance_pct,
        "threshold_pct": RECOMMENDATION_RELEVANCE_THRESHOLD,
        "meets_threshold": relevance_pct >= RECOMMENDATION_RELEVANCE_THRESHOLD,
    }


# --------------------------------------------------------- Combined report

def validation_report(db: Session) -> dict:
    """One-call payload combining all three Step 4 checks."""
    return {
        "forecast_accuracy": forecast_accuracy(db),
        "segmentation_quality": segmentation_quality(db),
        "recommendation_relevance": recommendation_relevance(db),
    }
