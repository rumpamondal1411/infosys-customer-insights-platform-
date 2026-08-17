"""
Milestone 2, Module 3 — Sales Analytics & Revenue Intelligence API.
Wraps app/services/revenue_intelligence_service.py, which aggregates
orders/payments/refunds/promotions into GMV, revenue growth, AOV, margin,
and region/time-segmented reports for the real-time dashboard.
"""
from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.database import get_db
from app.services import revenue_intelligence_service as ri

router = APIRouter(prefix="/revenue-intelligence", tags=["Revenue Intelligence"])


@router.get("/gmv-growth")
def gmv_and_growth(period_days: int = Query(30, ge=1, le=365), db: Session = Depends(get_db)):
    return ri.gmv_and_growth(db, period_days)


@router.get("/profit-margins")
def profit_margins(db: Session = Depends(get_db)):
    return ri.profit_margins(db)


@router.get("/refunds")
def refunds_summary(db: Session = Depends(get_db)):
    return ri.refunds_summary(db)


@router.get("/by-region")
def sales_by_region(db: Session = Depends(get_db)):
    return ri.sales_by_region(db)


@router.get("/by-time")
def sales_by_time_period(granularity: str = Query("daily", pattern="^(daily|weekly|monthly)$"),
                          db: Session = Depends(get_db)):
    return ri.sales_by_time_period(db, granularity)


@router.get("/promotion-performance")
def promotion_performance(db: Session = Depends(get_db)):
    return ri.promotion_performance(db)


@router.get("/dashboard")
def dashboard(period_days: int = Query(30, ge=1, le=365), db: Session = Depends(get_db)):
    """One-call payload for the real-time revenue intelligence dashboard page."""
    return ri.revenue_intelligence_dashboard(db, period_days)
