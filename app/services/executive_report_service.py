"""
Milestone 4 — Executive Reporting & Advanced BI.

This service does not introduce new analytics primitives; it composes the
outputs already produced by analytics_service, revenue_intelligence_service,
and customer_analytics_service (Milestones 1-3) into a single "executive
summary" payload — the KPI roll-up a stakeholder demo or a course evaluator
wants to see in one screen, plus a multi-sheet Excel workbook for offline
reporting.

Kept deliberately dependency-free (reuses pandas/openpyxl already in
requirements.txt) so no new packages need to be installed for Milestone 4.
"""
import os
from datetime import datetime

from sqlalchemy.orm import Session

from app.services import analytics_service, revenue_intelligence_service as ri
from app.services import customer_analytics_service as ca

EXEC_EXPORTS_DIR = "reports/executive"


def _ensure_exports_dir():
    os.makedirs(EXEC_EXPORTS_DIR, exist_ok=True)


def executive_summary(db: Session, period_days: int = 30) -> dict:
    """
    Single-call payload for the executive dashboard: top-line KPIs,
    growth, vendor/product leaders, customer health, and data-quality
    status — everything a Milestone 4 "executive reporting module" is
    expected to surface, without recomputing anything analytics_service
    or the Milestone 3 services already compute correctly.
    """
    summary = analytics_service.sales_summary(db)
    growth = ri.gmv_and_growth(db, period_days=period_days)
    vendor_perf = analytics_service.vendor_performance(db)
    top_products = analytics_service.top_products(db, limit=5)
    consistency = analytics_service.transactional_consistency_check(db)

    # Customer health — degrade gracefully if there isn't enough data yet
    # for K-Means (e.g. a freshly-seeded / near-empty database) rather than
    # letting the whole executive summary 500.
    try:
        segments = ca.segment_customers(db)
        segment_mix = segments["clusters"]
    except Exception:
        segment_mix = []

    try:
        churn = ca.churn_risk(db)
        high_risk_customers = len([c for c in churn if c["risk_level"] == "High"])
    except Exception:
        high_risk_customers = None

    top_vendor = max(vendor_perf, key=lambda v: v.get("total_revenue", 0)) if vendor_perf else None

    # Full ranked leaderboard for the "Top Vendor Performance" table — the
    # "Top Vendor" KPI card above only shows the #1 vendor, but the table
    # needs the ranked list. Previously this key was never added to the
    # payload, so the frontend's `summary.top_vendor_performance || []`
    # always fell back to an empty list even though `top_vendor` (the KPI
    # card) resolved correctly from the same `vendor_perf` data.
    top_vendor_performance = sorted(
        vendor_perf, key=lambda v: v.get("total_revenue", 0), reverse=True
    )[:10]

    return {
        "generated_at": datetime.utcnow().isoformat(),
        "period_days": period_days,
        "kpis": {
            "total_revenue": summary.get("total_revenue", 0),
            "total_orders": summary.get("total_orders", 0),
            "gmv": growth["gmv"],
            "average_order_value": growth["average_order_value"],
            "revenue_growth_pct": growth["revenue_growth_pct"],
            "active_vendor_count": len(vendor_perf),
            "high_churn_risk_customers": high_risk_customers,
        },
        "top_vendor": {
            "business_name": top_vendor.get("business_name"),
            "total_revenue": top_vendor.get("total_revenue"),
        } if top_vendor else None,
        "top_vendor_performance": top_vendor_performance,
        "top_products": top_products,
        "customer_segment_mix": segment_mix,
        "data_quality": consistency,
    }


def kpi_trend(db: Session, months: int = 6) -> list[dict]:
    """
    Monthly revenue/order-count trend for the executive line chart, built
    from the same daily time-series revenue_intelligence_service already
    produces (avoids re-querying transactions with a second pandas path).
    """
    daily = ri.sales_by_time_period(db, granularity="daily")
    if not daily:
        return []

    import pandas as pd
    df = pd.DataFrame(daily)
    if "transaction_date" not in df.columns:
        return []

    df["transaction_date"] = pd.to_datetime(df["transaction_date"])
    df["month"] = df["transaction_date"].dt.to_period("M").astype(str)

    monthly = (
        df.groupby("month")
        .agg(revenue=("total_revenue", "sum"), orders=("total_orders", "sum"))
        .reset_index()
        .sort_values("month")
        .tail(months)
    )
    monthly["revenue"] = monthly["revenue"].round(2)
    return monthly.to_dict(orient="records")


def export_executive_workbook(db: Session, period_days: int = 30) -> str:
    """
    Writes a single multi-sheet .xlsx (Summary, Vendor Performance, Top
    Products, Customer Segments, KPI Trend) — the "executive reporting"
    export a mentor demo can hand off as one file, instead of the
    per-section CSVs Milestone 3's report_service already covers.
    """
    import pandas as pd

    _ensure_exports_dir()

    summary = executive_summary(db, period_days=period_days)
    trend = kpi_trend(db)
    vendor_perf = analytics_service.vendor_performance(db)
    top_products = analytics_service.top_products(db, limit=20)

    timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
    path = os.path.join(EXEC_EXPORTS_DIR, f"executive_report_{timestamp}.xlsx")

    kpi_rows = [{"metric": k, "value": v} for k, v in summary["kpis"].items()]

    with pd.ExcelWriter(path, engine="openpyxl") as writer:
        pd.DataFrame(kpi_rows).to_excel(writer, sheet_name="Summary KPIs", index=False)
        pd.DataFrame(trend).to_excel(writer, sheet_name="KPI Trend", index=False)
        pd.DataFrame(vendor_perf).to_excel(writer, sheet_name="Vendor Performance", index=False)
        pd.DataFrame(top_products).to_excel(writer, sheet_name="Top Products", index=False)
        pd.DataFrame(summary["customer_segment_mix"]).to_excel(
            writer, sheet_name="Customer Segments", index=False
        )

    return path