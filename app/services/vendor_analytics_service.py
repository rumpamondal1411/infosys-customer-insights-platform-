"""
Vendor Analytics — per-vendor breakdown for the vendor-facing "Analytics"
page (as opposed to analytics_service, which rolls the same fact table up
to marketplace-wide numbers for admins).

Reuses the same Transaction/Product/Category fact table and the vendor_id
filter analytics_service._transactions_df already supports, so the numbers
here always agree with the admin-side reports for the same vendor.
"""
from typing import Optional

import pandas as pd
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.models.transaction import Transaction, TransactionStatus
from app.models.product import Product
from app.models.category import Category
from app.services.analytics_service import _transactions_df


def vendor_kpis(db: Session, vendor_id: int) -> dict:
    """High-level KPI cards for this vendor only."""
    df = _transactions_df(db, vendor_id=vendor_id)
    active_products = (
        db.query(func.count(Product.id))
        .filter(Product.vendor_id == vendor_id, Product.status == "active")
        .scalar()
        or 0
    )

    if df.empty:
        return {
            "total_revenue": 0.0,
            "total_orders": 0,
            "total_units_sold": 0,
            "average_order_value": 0.0,
            "unique_customers": 0,
            "active_products": int(active_products),
        }

    return {
        "total_revenue": round(float(df["total_amount"].sum()), 2),
        "total_orders": int(df.shape[0]),
        "total_units_sold": int(df["quantity"].sum()),
        "average_order_value": round(float(df["total_amount"].mean()), 2),
        "unique_customers": int(df["customer_id"].nunique()),
        "active_products": int(active_products),
    }


def monthly_revenue_trend(db: Session, vendor_id: int, months: int = 6) -> list[dict]:
    """Revenue + order count per month for this vendor's line chart."""
    df = _transactions_df(db, vendor_id=vendor_id)
    if df.empty:
        return []

    df["transaction_date"] = pd.to_datetime(df["transaction_date"])
    df["month"] = df["transaction_date"].dt.to_period("M").astype(str)

    monthly = (
        df.groupby("month")
        .agg(revenue=("total_amount", "sum"), orders=("id", "count"))
        .reset_index()
        .sort_values("month")
        .tail(months)
    )
    monthly["revenue"] = monthly["revenue"].round(2)
    return monthly.to_dict(orient="records")


def top_products(db: Session, vendor_id: int, limit: int = 5) -> list[dict]:
    """This vendor's own top-selling products by revenue — feeds the bar chart."""
    df = _transactions_df(db, vendor_id=vendor_id)
    if df.empty:
        return []

    grouped = (
        df.groupby(["product_id", "product_name"])
        .agg(
            total_revenue=("total_amount", "sum"),
            total_units_sold=("quantity", "sum"),
            total_orders=("id", "count"),
        )
        .reset_index()
        .sort_values("total_revenue", ascending=False)
        .head(limit)
    )
    grouped["total_revenue"] = grouped["total_revenue"].round(2)
    return grouped.to_dict(orient="records")


def category_breakdown(db: Session, vendor_id: int) -> list[dict]:
    """Revenue split across this vendor's product categories — feeds a pie chart."""
    df = _transactions_df(db, vendor_id=vendor_id)
    if df.empty:
        return []

    cat_map = {c.id: c.name for c in db.query(Category).all()}
    df["category_name"] = df["category_id"].map(cat_map).fillna("Uncategorized")

    grouped = (
        df.groupby("category_name")
        .agg(total_revenue=("total_amount", "sum"), total_orders=("id", "count"))
        .reset_index()
        .sort_values("total_revenue", ascending=False)
    )
    grouped["total_revenue"] = grouped["total_revenue"].round(2)
    return grouped.to_dict(orient="records")


def order_status_breakdown(db: Session, vendor_id: int) -> list[dict]:
    """
    Count of orders per fulfillment status (placed/shipped/delivered/
    cancelled/returned) for this vendor — feeds a pie chart. Unlike the
    revenue queries above this intentionally does NOT filter to
    TransactionStatus.COMPLETED, since cancelled/returned orders are
    exactly what this breakdown needs to show.
    """
    rows = (
        db.query(Transaction.order_status, func.count(Transaction.id))
        .filter(Transaction.vendor_id == vendor_id)
        .group_by(Transaction.order_status)
        .all()
    )
    return [
        {"status": status.value if hasattr(status, "value") else status, "count": count}
        for status, count in rows
    ]


def vendor_analytics_summary(db: Session, vendor_id: int, months: int = 6) -> dict:
    """Single-call payload for the vendor Analytics page."""
    return {
        "kpis": vendor_kpis(db, vendor_id),
        "monthly_revenue_trend": monthly_revenue_trend(db, vendor_id, months=months),
        "top_products": top_products(db, vendor_id, limit=5),
        "category_breakdown": category_breakdown(db, vendor_id),
        "order_status_breakdown": order_status_breakdown(db, vendor_id),
    }


def export_vendor_report_csv(db: Session, vendor_id: int, months: int = 6) -> str:
    """
    Builds a single CSV report for this vendor — KPI summary, monthly
    revenue trend, top products, category breakdown, and order-status
    mix, each as its own labelled section — and writes it to /tmp.
    Returns the file path.
    """
    import csv
    import os
    import tempfile
    from datetime import datetime

    kpis = vendor_kpis(db, vendor_id)
    trend = monthly_revenue_trend(db, vendor_id, months=months)
    products = top_products(db, vendor_id, limit=5)
    categories = category_breakdown(db, vendor_id)
    statuses = order_status_breakdown(db, vendor_id)

    fd, path = tempfile.mkstemp(
        suffix=".csv", prefix=f"vendor_{vendor_id}_report_"
    )
    os.close(fd)

    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)

        writer.writerow([f"Vendor Analytics Report — Vendor ID {vendor_id}"])
        writer.writerow([f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"])
        writer.writerow([])

        writer.writerow(["KPI Summary"])
        writer.writerow(["Metric", "Value"])
        for key, value in kpis.items():
            writer.writerow([key.replace("_", " ").title(), value])
        writer.writerow([])

        writer.writerow(["Monthly Revenue Trend"])
        writer.writerow(["Month", "Revenue", "Orders"])
        for row in trend:
            writer.writerow([row.get("month"), row.get("revenue"), row.get("orders")])
        writer.writerow([])

        writer.writerow(["Top Products"])
        writer.writerow(["Product", "Revenue", "Units Sold", "Orders"])
        for row in products:
            writer.writerow([
                row.get("product_name"), row.get("total_revenue"),
                row.get("total_units_sold"), row.get("total_orders"),
            ])
        writer.writerow([])

        writer.writerow(["Revenue by Category"])
        writer.writerow(["Category", "Revenue", "Orders"])
        for row in categories:
            writer.writerow([row.get("category_name"), row.get("total_revenue"), row.get("total_orders")])
        writer.writerow([])

        writer.writerow(["Order Status Mix"])
        writer.writerow(["Status", "Count"])
        for row in statuses:
            writer.writerow([row.get("status"), row.get("count")])

    return path
