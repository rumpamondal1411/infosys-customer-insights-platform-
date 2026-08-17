"""
Milestone 2 — Module 3: Sales Analytics & Revenue Intelligence.

Builds on the Week 1 aggregation engine (app/services/analytics_service.py)
to add the specific Milestone 2 requirements:
  - Aggregating orders, payments, refunds AND promotional campaigns.
  - Segmented reports by vendor / product / category / region / time period.
  - Revenue growth, GMV, average order value, and gross profit margin.
  - Data that a real-time operational/strategic dashboard can be built on
    (see /revenue-intelligence-page).
"""
from datetime import datetime, timedelta
from typing import Optional

import pandas as pd
from sqlalchemy.orm import Session

from app.models.transaction import Transaction, TransactionStatus
from app.models.product import Product
from app.models.vendor import Vendor
from app.models.category import Category
from app.models.promotion import Promotion


def _all_transactions_df(db: Session) -> pd.DataFrame:
    """Every transaction regardless of status — needed for refunds/cancellations."""
    rows = (
        db.query(
            Transaction.id,
            Transaction.vendor_id,
            Transaction.product_id,
            Transaction.customer_id,
            Transaction.quantity,
            Transaction.unit_price,
            Transaction.total_amount,
            Transaction.discount_amount,
            Transaction.promotion_id,
            Transaction.status,
            Transaction.transaction_date,
            Product.name.label("product_name"),
            Product.cost_price,
            Product.category_id,
            Vendor.business_name,
            Vendor.country,
        )
        .join(Product, Transaction.product_id == Product.id)
        .join(Vendor, Transaction.vendor_id == Vendor.id)
        .all()
    )
    cols = [
        "id", "vendor_id", "product_id", "customer_id", "quantity", "unit_price",
        "total_amount", "discount_amount", "promotion_id", "status", "transaction_date",
        "product_name", "cost_price", "category_id", "business_name", "country",
    ]
    if not rows:
        return pd.DataFrame(columns=cols)
    df = pd.DataFrame(rows, columns=cols)
    df["transaction_date"] = pd.to_datetime(df["transaction_date"])
    return df


def _completed(df: pd.DataFrame) -> pd.DataFrame:
    return df[df["status"] == TransactionStatus.COMPLETED]


def gmv_and_growth(db: Session, period_days: int = 30) -> dict:
    """
    Gross Merchandise Value, revenue, AOV, and period-over-period growth.
    Compares the trailing `period_days` window against the equal-length
    window immediately before it.
    """
    df = _completed(_all_transactions_df(db))
    if df.empty:
        return {
            "gmv": 0.0, "revenue": 0.0, "average_order_value": 0.0,
            "current_period_revenue": 0.0, "previous_period_revenue": 0.0,
            "revenue_growth_pct": 0.0, "period_days": period_days,
        }

    now = df["transaction_date"].max()
    current_start = now - timedelta(days=period_days)
    previous_start = current_start - timedelta(days=period_days)

    current = df[df["transaction_date"] >= current_start]
    previous = df[(df["transaction_date"] >= previous_start) & (df["transaction_date"] < current_start)]

    current_revenue = round(float(current["total_amount"].sum()), 2)
    previous_revenue = round(float(previous["total_amount"].sum()), 2)

    if previous_revenue > 0:
        growth_pct = round((current_revenue - previous_revenue) / previous_revenue * 100, 2)
    else:
        growth_pct = 100.0 if current_revenue > 0 else 0.0

    # GMV = total value of merchandise sold, before marketplace commission is netted out.
    gmv = round(float(df["total_amount"].sum()) + float(df["discount_amount"].sum()), 2)

    return {
        "gmv": gmv,
        "revenue": round(float(df["total_amount"].sum()), 2),
        "average_order_value": round(float(df["total_amount"].mean()), 2),
        "current_period_revenue": current_revenue,
        "previous_period_revenue": previous_revenue,
        "revenue_growth_pct": growth_pct,
        "period_days": period_days,
    }


def profit_margins(db: Session) -> list[dict]:
    """
    Gross profit margin per product = (price - cost_price) / price, applied to
    actual units sold, so vendors/analysts see realized margin, not list-price margin.
    """
    df = _completed(_all_transactions_df(db))
    if df.empty:
        return []

    df = df.dropna(subset=["cost_price"])
    if df.empty:
        return []

    df["revenue"] = df["total_amount"]
    df["cost_total"] = df["cost_price"] * df["quantity"]
    df["profit"] = df["revenue"] - df["cost_total"]

    grouped = (
        df.groupby(["product_id", "product_name"])
        .agg(
            revenue=("revenue", "sum"),
            cost_total=("cost_total", "sum"),
            profit=("profit", "sum"),
            units_sold=("quantity", "sum"),
        )
        .reset_index()
    )
    grouped["margin_pct"] = (grouped["profit"] / grouped["revenue"] * 100).round(2)
    for col in ("revenue", "cost_total", "profit"):
        grouped[col] = grouped[col].round(2)
    grouped = grouped.sort_values("profit", ascending=False)
    return grouped.to_dict(orient="records")


def refunds_summary(db: Session) -> dict:
    """Aggregates refunded/cancelled transactions — the 'refunds' data source."""
    df = _all_transactions_df(db)
    if df.empty:
        return {"total_refunded_amount": 0.0, "refund_count": 0, "cancelled_count": 0, "refund_rate_pct": 0.0}

    refunded = df[df["status"] == TransactionStatus.REFUNDED]
    cancelled = df[df["status"] == TransactionStatus.CANCELLED]
    total_orders = df.shape[0]

    return {
        "total_refunded_amount": round(float(refunded["total_amount"].sum()), 2),
        "refund_count": int(refunded.shape[0]),
        "cancelled_count": int(cancelled.shape[0]),
        "refund_rate_pct": round(refunded.shape[0] / total_orders * 100, 2) if total_orders else 0.0,
    }


def sales_by_region(db: Session) -> list[dict]:
    """Segmented report by region — vendor.country is used as the region proxy."""
    df = _completed(_all_transactions_df(db))
    if df.empty:
        return []
    df["region"] = df["country"].fillna("Unknown")
    grouped = (
        df.groupby("region")
        .agg(
            total_revenue=("total_amount", "sum"),
            total_orders=("id", "count"),
            total_units_sold=("quantity", "sum"),
        )
        .reset_index()
        .sort_values("total_revenue", ascending=False)
    )
    grouped["total_revenue"] = grouped["total_revenue"].round(2)
    return grouped.to_dict(orient="records")


def sales_by_time_period(db: Session, granularity: str = "daily") -> list[dict]:
    """Segmented report by time period — supports daily / weekly / monthly rollups."""
    df = _completed(_all_transactions_df(db))
    if df.empty:
        return []

    freq_map = {"daily": "D", "weekly": "W", "monthly": "ME"}
    freq = freq_map.get(granularity, "D")

    grouped = (
        df.set_index("transaction_date")
        .resample(freq)
        .agg(total_revenue=("total_amount", "sum"), total_orders=("id", "count"), total_units_sold=("quantity", "sum"))
        .reset_index()
    )
    grouped = grouped[grouped["total_orders"] > 0]
    grouped["total_revenue"] = grouped["total_revenue"].round(2)
    grouped["transaction_date"] = grouped["transaction_date"].dt.strftime("%Y-%m-%d")
    return grouped.to_dict(orient="records")


def promotion_performance(db: Session) -> list[dict]:
    """Aggregates transaction data attributable to each promotional campaign."""
    df = _completed(_all_transactions_df(db))
    promos = {p.id: p for p in db.query(Promotion).all()}

    used = df.dropna(subset=["promotion_id"])
    results = []
    for promo_id, group in used.groupby("promotion_id"):
        promo = promos.get(int(promo_id))
        results.append({
            "promotion_id": int(promo_id),
            "code": promo.code if promo else "Unknown",
            "orders": int(group.shape[0]),
            "units_sold": int(group["quantity"].sum()),
            "revenue": round(float(group["total_amount"].sum()), 2),
            "total_discount_given": round(float(group["discount_amount"].sum()), 2),
        })
    results.sort(key=lambda r: r["revenue"], reverse=True)
    return results


def marketplace_benchmark(db: Session, vendor_id: Optional[int] = None) -> list[dict]:
    """
    Milestone 3 — marketplace benchmarking: how each vendor's revenue, order
    volume, and average order value compare to the marketplace-wide average,
    expressed as a percentile rank so vendors can see "you're in the top X%"
    rather than just a raw number.
    """
    df = _completed(_all_transactions_df(db))
    if df.empty:
        return []

    grouped = (
        df.groupby("vendor_id")
        .agg(
            total_revenue=("total_amount", "sum"),
            total_orders=("id", "count"),
            units_sold=("quantity", "sum"),
        )
        .reset_index()
    )
    grouped["avg_order_value"] = (grouped["total_revenue"] / grouped["total_orders"]).round(2)

    marketplace_avg_revenue = grouped["total_revenue"].mean()
    marketplace_avg_orders = grouped["total_orders"].mean()
    marketplace_avg_aov = grouped["avg_order_value"].mean()

    grouped["revenue_percentile"] = grouped["total_revenue"].rank(pct=True).mul(100).round(1)
    grouped["orders_percentile"] = grouped["total_orders"].rank(pct=True).mul(100).round(1)

    grouped["revenue_vs_marketplace_avg_pct"] = (
        (grouped["total_revenue"] - marketplace_avg_revenue) / marketplace_avg_revenue * 100
    ).round(1)
    grouped["orders_vs_marketplace_avg_pct"] = (
        (grouped["total_orders"] - marketplace_avg_orders) / marketplace_avg_orders * 100
    ).round(1)
    grouped["aov_vs_marketplace_avg_pct"] = (
        (grouped["avg_order_value"] - marketplace_avg_aov) / marketplace_avg_aov * 100
    ).round(1)

    grouped["total_revenue"] = grouped["total_revenue"].round(2)

    if vendor_id is not None:
        grouped = grouped[grouped["vendor_id"] == vendor_id]

    grouped = grouped.sort_values("total_revenue", ascending=False)
    return grouped.to_dict(orient="records")


def revenue_intelligence_dashboard(db: Session, period_days: int = 30) -> dict:
    """One-call payload for the real-time revenue intelligence dashboard page."""
    return {
        "gmv_and_growth": gmv_and_growth(db, period_days),
        "refunds": refunds_summary(db),
        "sales_by_region": sales_by_region(db),
        "sales_by_time": sales_by_time_period(db, "daily"),
        "top_margin_products": profit_margins(db)[:10],
        "promotion_performance": promotion_performance(db),
    }
