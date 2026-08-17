"""
Report service — generates the "baseline marketplace analytics report"
required for Week 1: revenue + product performance metrics exported to
disk as CSV and JSON so they can be attached to stakeholder updates or
picked up by a later BI/export module (Week 6 deliverable).
"""
import json
import os
from datetime import datetime

from sqlalchemy.orm import Session

from app.services import analytics_service

REPORTS_DIR = "reports"


def _ensure_reports_dir():
    os.makedirs(REPORTS_DIR, exist_ok=True)


def generate_baseline_report(db: Session) -> dict:
    """
    Builds the Week 1 baseline report combining:
      - marketplace-wide sales summary
      - revenue by vendor
      - revenue by category
      - top 10 products
      - vendor performance snapshot
      - inventory turnover snapshot

    Writes both a JSON file (full detail) and a set of CSV files (one per
    section) into /reports, and returns the in-memory report dict.
    """
    _ensure_reports_dir()
    timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")

    report = {
        "generated_at": datetime.utcnow().isoformat(),
        "summary": analytics_service.sales_summary(db),
        "revenue_by_vendor": analytics_service.revenue_by_vendor(db),
        "revenue_by_category": analytics_service.revenue_by_category(db),
        "top_products": analytics_service.top_products(db, limit=10),
        "vendor_performance": analytics_service.vendor_performance(db),
        "inventory_turnover": analytics_service.inventory_turnover(db),
        "consistency_check": analytics_service.transactional_consistency_check(db),
    }

    json_path = os.path.join(REPORTS_DIR, f"baseline_report_{timestamp}.json")
    with open(json_path, "w") as f:
        json.dump(report, f, indent=2, default=str)

    import pandas as pd
    for section in ["revenue_by_vendor", "revenue_by_category", "top_products",
                     "vendor_performance", "inventory_turnover"]:
        data = report[section]
        csv_path = os.path.join(REPORTS_DIR, f"{section}_{timestamp}.csv")
        if data:
            pd.DataFrame(data).to_csv(csv_path, index=False)
        else:
            pd.DataFrame().to_csv(csv_path, index=False)

    report["_files"] = {
        "json": json_path,
        "csv_prefix": f"{REPORTS_DIR}/*_{timestamp}.csv",
    }
    return report


# ------------------------------------------------------------------
# Milestone 3 — on-demand report export (CSV / Excel) & scheduled reports
# ------------------------------------------------------------------

EXPORTS_DIR = "reports/exports"

# Maps a report "section" name (as exposed via the API) to the service call
# that produces it, so new sections only need one line added here.
def _section_builders():
    from app.services import revenue_intelligence_service as ri
    return {
        "revenue_by_vendor": lambda db: analytics_service.revenue_by_vendor(db),
        "revenue_by_category": lambda db: analytics_service.revenue_by_category(db),
        "top_products": lambda db: analytics_service.top_products(db, limit=20),
        "vendor_performance": lambda db: analytics_service.vendor_performance(db),
        "inventory_turnover": lambda db: analytics_service.inventory_turnover(db),
        "marketplace_benchmark": lambda db: ri.marketplace_benchmark(db),
        "profit_margins": lambda db: ri.profit_margins(db),
    }


def _ensure_exports_dir():
    os.makedirs(EXPORTS_DIR, exist_ok=True)


def export_section(db: Session, section: str, fmt: str = "csv") -> str:
    """
    Builds the requested analytics section fresh and writes it to disk in
    the requested format. Returns the file path so the caller (API layer)
    can stream it back as a download.
    """
    builders = _section_builders()
    if section not in builders:
        raise ValueError(f"Unknown report section '{section}'. Available: {list(builders)}")
    if fmt not in ("csv", "xlsx"):
        raise ValueError("fmt must be 'csv' or 'xlsx'")

    _ensure_exports_dir()
    import pandas as pd

    data = builders[section](db)
    df = pd.DataFrame(data) if data else pd.DataFrame()

    timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
    path = os.path.join(EXPORTS_DIR, f"{section}_{timestamp}.{fmt}")

    if fmt == "csv":
        df.to_csv(path, index=False)
    else:
        df.to_excel(path, index=False, engine="openpyxl")

    return path


def generate_scheduled_report(db: Session) -> dict:
    """
    The 'scheduled analytical pipeline execution' report — a superset of the
    Week 1 baseline report that also includes the Milestone 2/3 revenue
    intelligence and marketplace benchmarking sections. Called by the
    APScheduler job in app/scheduler.py, or on demand via the API.
    """
    from app.services import revenue_intelligence_service

    report = generate_baseline_report(db)
    report["marketplace_benchmark"] = revenue_intelligence_service.marketplace_benchmark(db)
    report["profit_margins"] = revenue_intelligence_service.profit_margins(db)
    report["gmv_and_growth"] = revenue_intelligence_service.gmv_and_growth(db)

    _ensure_reports_dir()
    timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
    extended_path = os.path.join(REPORTS_DIR, f"scheduled_report_{timestamp}.json")
    with open(extended_path, "w") as f:
        json.dump(report, f, indent=2, default=str)
    report["_files"]["extended_json"] = extended_path
    return report
