"""
Milestone 2, Module 4 — Customer Behaviour & Recommendation Analytics API.
Wraps app/services/customer_analytics_service.py: segmentation (KMeans),
personalized recommendations (collaborative + content-based filtering),
and churn-risk scoring.
"""
from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.database import get_db
from app.services import customer_analytics_service as ca

router = APIRouter(prefix="/customer-analytics", tags=["Customer Behaviour & Recommendation Analytics"])


@router.get("/segments")
def segments(n_clusters: int = Query(4, ge=2, le=8), db: Session = Depends(get_db)):
    return ca.segment_customers(db, n_clusters)


@router.get("/customer/{customer_id}/profile")
def profile(customer_id: int, db: Session = Depends(get_db)):
    return ca.customer_profile(db, customer_id)


@router.get("/customer/{customer_id}/revenue-analysis")
def customer_revenue_analysis(customer_id: int, db: Session = Depends(get_db)):
    """Customer-facing 'My Spending' revenue analysis: total spend, monthly trend, category breakdown."""
    return ca.customer_revenue_analysis(db, customer_id)


@router.get("/recommendations/{customer_id}")
def recommendations(customer_id: int, top_n: int = Query(8, ge=1, le=20), db: Session = Depends(get_db)):
    return ca.recommend_for_customer(db, customer_id, top_n)


@router.get("/churn-risk")
def churn_risk(db: Session = Depends(get_db)):
    return ca.churn_risk(db)


@router.get("/dashboard")
def dashboard(db: Session = Depends(get_db)):
    """One-call payload for the admin-facing Customer Analytics dashboard page."""
    return ca.customer_analytics_dashboard(db)
