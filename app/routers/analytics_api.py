"""
Milestone 3 — API, Reporting & CI Integration.

This router is the "control plane" added in Milestone 3: it exposes the
ETL pipeline, the MLflow-tracked training job, marketplace benchmarking,
and report export/scheduling as REST endpoints, on top of the existing
vendor/product/revenue/customer analytics APIs from Milestones 1-2 (which
already live in their own routers — vendors, products, inventory,
revenue_intelligence, customer_analytics).
"""
from typing import Optional

from fastapi import APIRouter, Depends, Query, HTTPException, status
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.analytics_snapshot import PipelineRun, VendorPerformanceSnapshot, CustomerSegmentSnapshot
from app.services import revenue_intelligence_service, report_service
from app.etl.pipeline import run_pipeline
from app.ml import segmentation_training

router = APIRouter(prefix="/api/v1", tags=["Milestone 3 — Analytics Infrastructure & Reporting"])


# ------------------------------------------------------------------ ETL

@router.post("/etl/run")
def trigger_etl(db: Session = Depends(get_db)):
    """Manually triggers the extract -> clean -> aggregate -> load pipeline."""
    try:
        return run_pipeline(db, triggered_by="manual")
    except Exception as exc:
        raise HTTPException(status.HTTP_500_INTERNAL_SERVER_ERROR, f"ETL pipeline failed: {exc}")


@router.get("/etl/runs")
def list_etl_runs(limit: int = Query(20, ge=1, le=200), db: Session = Depends(get_db)):
    """Audit history of ETL pipeline executions (manual or scheduled)."""
    runs = (
        db.query(PipelineRun)
        .order_by(PipelineRun.started_at.desc())
        .limit(limit)
        .all()
    )
    return [
        {
            "id": r.id,
            "pipeline_name": r.pipeline_name,
            "triggered_by": r.triggered_by,
            "status": r.status.value,
            "started_at": r.started_at,
            "finished_at": r.finished_at,
            "rows_extracted": r.rows_extracted,
            "rows_loaded": r.rows_loaded,
            "error_message": r.error_message,
            "summary": r.summary,
        }
        for r in runs
    ]


@router.get("/etl/vendor-snapshots")
def vendor_snapshots(vendor_id: Optional[int] = None, limit: int = Query(50, ge=1, le=500),
                      db: Session = Depends(get_db)):
    """Versioned vendor performance snapshots produced by the ETL load stage."""
    q = db.query(VendorPerformanceSnapshot)
    if vendor_id is not None:
        q = q.filter(VendorPerformanceSnapshot.vendor_id == vendor_id)
    rows = q.order_by(VendorPerformanceSnapshot.snapshot_date.desc()).limit(limit).all()
    return [
        {
            "id": r.id,
            "pipeline_run_id": r.pipeline_run_id,
            "vendor_id": r.vendor_id,
            "snapshot_date": r.snapshot_date,
            "total_revenue": r.total_revenue,
            "total_orders": r.total_orders,
            "avg_order_value": r.avg_order_value,
            "units_sold": r.units_sold,
        }
        for r in rows
    ]


# --------------------------------------------------------------- ML / MLflow

@router.post("/ml/segmentation/train")
def train_segmentation_model(n_clusters: int = Query(4, ge=2, le=8), db: Session = Depends(get_db)):
    """
    Trains the RFM K-Means customer segmentation model with full MLflow
    experiment tracking, registers it to the MLflow Model Registry, and
    persists a versioned snapshot of the resulting segments.
    """
    result = segmentation_training.train_and_register(db, n_clusters=n_clusters)
    if not result.get("trained"):
        raise HTTPException(status.HTTP_400_BAD_REQUEST, result.get("reason", "Training skipped"))
    return result


@router.get("/ml/segmentation/runs")
def list_segmentation_runs(limit: int = Query(20, ge=1, le=100), db: Session = Depends(get_db)):
    """Local audit trail of training runs (mirrors what's logged in MLflow)."""
    runs = segmentation_training.list_model_runs(db, limit=limit)
    return [
        {
            "id": r.id,
            "model_name": r.model_name,
            "mlflow_run_id": r.mlflow_run_id,
            "version": r.version,
            "params": r.params,
            "metrics": r.metrics,
            "trained_at": r.trained_at,
            "registered": r.registered,
        }
        for r in runs
    ]


@router.get("/ml/segmentation/latest-version")
def latest_segmentation_version():
    """Queries the MLflow Model Registry for the most recently registered version."""
    result = segmentation_training.get_latest_registered_version()
    if result is None:
        raise HTTPException(
            status.HTTP_404_NOT_FOUND,
            "No registered model versions found yet — run POST /api/v1/ml/segmentation/train first.",
        )
    return result


@router.get("/ml/segmentation/snapshots")
def segmentation_snapshots(customer_id: Optional[int] = None, limit: int = Query(100, ge=1, le=1000),
                            db: Session = Depends(get_db)):
    """Versioned customer segment assignments from past training runs."""
    q = db.query(CustomerSegmentSnapshot)
    if customer_id is not None:
        q = q.filter(CustomerSegmentSnapshot.customer_id == customer_id)
    rows = q.order_by(CustomerSegmentSnapshot.snapshot_date.desc()).limit(limit).all()
    return [
        {
            "customer_id": r.customer_id,
            "segment_label": r.segment_label,
            "recency_days": r.recency_days,
            "frequency": r.frequency,
            "monetary": r.monetary,
            "snapshot_date": r.snapshot_date,
        }
        for r in rows
    ]


# ------------------------------------------------------- Marketplace benchmarking

@router.get("/benchmark/marketplace")
def marketplace_benchmark(vendor_id: Optional[int] = None, db: Session = Depends(get_db)):
    """
    Advanced revenue analysis & marketplace benchmarking: how each vendor's
    revenue, order volume, and AOV compare to the marketplace-wide average
    and percentile rank.
    """
    return revenue_intelligence_service.marketplace_benchmark(db, vendor_id=vendor_id)


# ------------------------------------------------------------------- Reporting

@router.get("/reports/export")
def export_report(
    section: str = Query(..., description="revenue_by_vendor | revenue_by_category | top_products | "
                                            "vendor_performance | inventory_turnover | marketplace_benchmark | profit_margins"),
    fmt: str = Query("csv", pattern="^(csv|xlsx)$"),
    db: Session = Depends(get_db),
):
    """Generates and downloads a fresh export of one analytics section as CSV or Excel."""
    try:
        path = report_service.export_section(db, section, fmt)
    except ValueError as exc:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, str(exc))
    media_type = "text/csv" if fmt == "csv" else "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    return FileResponse(path, media_type=media_type, filename=path.split("/")[-1])


@router.post("/reports/scheduled/run")
def run_scheduled_report_now(db: Session = Depends(get_db)):
    """Manually triggers the same extended report the nightly scheduler generates."""
    report = report_service.generate_scheduled_report(db)
    return {"generated_at": report["generated_at"], "files": report["_files"]}
