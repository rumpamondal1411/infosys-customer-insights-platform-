"""
Milestone 2, Step 4 — Validation API.
Wraps app/services/validation_service.py: backtested forecast accuracy,
clustering-quality (silhouette) for segmentation, and leave-one-out
recommendation relevance, each checked against the mentor's thresholds.
"""
from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.database import get_db
from app.services import validation_service as validation

router = APIRouter(prefix="/validation", tags=["Validation"])


@router.get("/forecast-accuracy")
def forecast_accuracy(horizon_days: int = Query(7, ge=1, le=90), db: Session = Depends(get_db)):
    return validation.forecast_accuracy(db, horizon_days)


@router.get("/segmentation-quality")
def segmentation_quality(n_clusters: int = Query(4, ge=2, le=8), db: Session = Depends(get_db)):
    return validation.segmentation_quality(db, n_clusters)


@router.get("/recommendation-relevance")
def recommendation_relevance(top_n: int = Query(8, ge=1, le=20), db: Session = Depends(get_db)):
    return validation.recommendation_relevance(db, top_n)


@router.get("/report")
def report(db: Session = Depends(get_db)):
    """One-call payload for the validation dashboard page."""
    return validation.validation_report(db)
