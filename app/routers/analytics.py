"""
Analytics API — sales aggregation, vendor performance, inventory turnover,
demand forecasting, and the baseline marketplace report generator.
"""
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.database import get_db
from app.services import analytics_service, report_service

router = APIRouter(
    prefix="/analytics",
    tags=["Sales & Marketplace Analytics"]
)


# ==========================================================
# Existing Analytics APIs
# ==========================================================

@router.get("/sales-summary")
def sales_summary(db: Session = Depends(get_db)):
    return analytics_service.sales_summary(db)


@router.get("/revenue-by-vendor")
def revenue_by_vendor(db: Session =Depends(get_db)):
    return analytics_service.revenue_by_vendor(db)


@router.get("/revenue-by-category")
def revenue_by_category(db: Session = Depends(get_db)):
    return analytics_service.revenue_by_category(db)


@router.get("/top-products")
def top_products(limit: int = 10, db: Session = Depends(get_db)):
    return analytics_service.top_products(db, limit)


@router.get("/vendor-performance")
def vendor_performance(db: Session = Depends(get_db)):
    return analytics_service.vendor_performance(db)


@router.get("/inventory-turnover")
def inventory_turnover(db: Session = Depends(get_db)):
    return analytics_service.inventory_turnover(db)


@router.get("/consistency-check")
def consistency_check(db: Session = Depends(get_db)):
    return analytics_service.transactional_consistency_check(db)


@router.get("/forecast/{product_id}")
def demand_forecast(
    product_id: int,
    days_history: int = 30,
    db: Session = Depends(get_db)
):
    return analytics_service.simple_demand_forecast(
        db,
        product_id,
        days_history
    )


@router.post("/reports/baseline")
def generate_baseline_report(db: Session = Depends(get_db)):
    return report_service.generate_baseline_report(db)


# ==========================================================
# Analytics Dashboard APIs
# ==========================================================

@router.get("/dashboard-stats")
def dashboard_stats(db: Session = Depends(get_db)):
    return analytics_service.dashboard_stats(db)


@router.get("/low-stock")
def low_stock(db: Session = Depends(get_db)):
    return analytics_service.low_stock_products(db)


@router.get("/recent-transactions")
def recent_transactions(db: Session = Depends(get_db)):
    return analytics_service.recent_transactions(db)