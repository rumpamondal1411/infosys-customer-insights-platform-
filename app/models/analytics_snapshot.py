"""
Milestone 3 — Data Management & Analytics Infrastructure.

These models give the ETL pipeline and ML training jobs somewhere durable
to record *what ran, when, and with what result* — separate from the raw
Transaction fact table. This is what lets scheduled jobs be inspected /
audited later, and lets analytical outputs be versioned rather than only
ever existing as the "latest" in-memory computation.
"""
import enum
from datetime import datetime
from typing import Optional

from sqlalchemy import Integer, String, Float, DateTime, Enum, Text, JSON
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class PipelineStatus(str, enum.Enum):
    RUNNING = "running"
    SUCCESS = "success"
    FAILED = "failed"


class PipelineRun(Base):
    """One row per ETL pipeline execution (manual or scheduled)."""

    __tablename__ = "pipeline_runs"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    pipeline_name: Mapped[str] = mapped_column(String(100), default="core_etl", index=True)
    triggered_by: Mapped[str] = mapped_column(String(50), default="manual")  # manual | scheduler
    status: Mapped[PipelineStatus] = mapped_column(
        Enum(PipelineStatus), default=PipelineStatus.RUNNING, nullable=False
    )
    started_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    finished_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    rows_extracted: Mapped[int] = mapped_column(Integer, default=0)
    rows_loaded: Mapped[int] = mapped_column(Integer, default=0)
    error_message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    summary: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)

    def __repr__(self) -> str:
        return f"<PipelineRun id={self.id} name={self.pipeline_name} status={self.status}>"


class VendorPerformanceSnapshot(Base):
    """
    A versioned, point-in-time roll-up of vendor performance produced by the
    ETL 'aggregate' stage. Historical rows are kept (not overwritten) so
    trends can be tracked across pipeline runs.
    """

    __tablename__ = "vendor_performance_snapshots"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    pipeline_run_id: Mapped[Optional[int]] = mapped_column(Integer, nullable=True, index=True)
    vendor_id: Mapped[int] = mapped_column(Integer, index=True)
    snapshot_date: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, index=True)
    total_revenue: Mapped[float] = mapped_column(Float, default=0.0)
    total_orders: Mapped[int] = mapped_column(Integer, default=0)
    avg_order_value: Mapped[float] = mapped_column(Float, default=0.0)
    units_sold: Mapped[int] = mapped_column(Integer, default=0)


class CustomerSegmentSnapshot(Base):
    """Versioned output of the RFM/K-Means segmentation model per run."""

    __tablename__ = "customer_segment_snapshots"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    pipeline_run_id: Mapped[Optional[int]] = mapped_column(Integer, nullable=True, index=True)
    customer_id: Mapped[int] = mapped_column(Integer, index=True)
    segment_label: Mapped[str] = mapped_column(String(50))
    recency_days: Mapped[float] = mapped_column(Float, default=0.0)
    frequency: Mapped[float] = mapped_column(Float, default=0.0)
    monetary: Mapped[float] = mapped_column(Float, default=0.0)
    snapshot_date: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, index=True)


class MLModelRun(Base):
    """
    Lightweight local record of a model training run, mirroring what's
    logged to MLflow — kept in-app too so the API can list model history
    without round-tripping to the MLflow tracking server on every request.
    """

    __tablename__ = "ml_model_runs"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    model_name: Mapped[str] = mapped_column(String(100), index=True)
    mlflow_run_id: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    version: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)
    params: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    metrics: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    trained_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    registered: Mapped[bool] = mapped_column(default=False)
