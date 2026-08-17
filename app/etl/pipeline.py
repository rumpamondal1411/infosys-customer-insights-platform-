"""
Milestone 3 — ETL pipeline.

Extract  -> pull raw Transaction (+ Product/Vendor) rows into a DataFrame.
Transform -> clean nulls/negative quantities, cast types, derive net revenue.
Aggregate -> roll up into vendor performance metrics.
Load     -> persist the aggregate as a new, timestamped snapshot row (never
            overwritten) plus a PipelineRun audit record.

This mirrors what a real ELT/ETL job (Airflow/Prefect/dbt) would do, scaled
down to something that runs in-process for the assignment: no external
orchestrator is required, but the four stages are kept as separate,
independently-testable functions.
"""
from datetime import datetime
from typing import Optional

import pandas as pd
from sqlalchemy.orm import Session

from app.models.transaction import Transaction, TransactionStatus
from app.models.analytics_snapshot import (
    PipelineRun, PipelineStatus, VendorPerformanceSnapshot,
)


def extract(db: Session) -> pd.DataFrame:
    """Pull every transaction row into a flat DataFrame."""
    rows = db.query(
        Transaction.id,
        Transaction.vendor_id,
        Transaction.product_id,
        Transaction.customer_id,
        Transaction.quantity,
        Transaction.unit_price,
        Transaction.total_amount,
        Transaction.discount_amount,
        Transaction.status,
        Transaction.transaction_date,
    ).all()

    df = pd.DataFrame(rows, columns=[
        "id", "vendor_id", "product_id", "customer_id", "quantity",
        "unit_price", "total_amount", "discount_amount", "status",
        "transaction_date",
    ])
    return df


def clean_transform(df: pd.DataFrame) -> pd.DataFrame:
    """
    Cleansing rules:
      - drop rows missing a vendor_id or product_id (can't be attributed)
      - coerce numeric columns, drop negative quantity/price rows
      - keep only COMPLETED transactions for revenue aggregation
      - derive `net_revenue` = total_amount (already discount-net) with any
        remaining NaNs filled to 0
    """
    if df.empty:
        return df

    df = df.dropna(subset=["vendor_id", "product_id"]).copy()

    for col in ["quantity", "unit_price", "total_amount", "discount_amount"]:
        df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0)

    df = df[(df["quantity"] > 0) & (df["unit_price"] >= 0)]

    df["status"] = df["status"].astype(str).str.lower()
    df = df[df["status"] == TransactionStatus.COMPLETED.value]

    df["net_revenue"] = df["total_amount"].fillna(0)
    df["transaction_date"] = pd.to_datetime(df["transaction_date"], errors="coerce")
    df = df.dropna(subset=["transaction_date"])

    return df


def aggregate(df: pd.DataFrame) -> pd.DataFrame:
    """Roll cleaned transaction rows up into one row per vendor."""
    if df.empty:
        return pd.DataFrame(columns=[
            "vendor_id", "total_revenue", "total_orders", "avg_order_value", "units_sold",
        ])

    grouped = df.groupby("vendor_id").agg(
        total_revenue=("net_revenue", "sum"),
        total_orders=("id", "count"),
        units_sold=("quantity", "sum"),
    ).reset_index()
    grouped["avg_order_value"] = (grouped["total_revenue"] / grouped["total_orders"]).round(2)
    grouped["total_revenue"] = grouped["total_revenue"].round(2)
    return grouped


def load(db: Session, aggregated: pd.DataFrame, pipeline_run_id: int) -> int:
    """Persist the aggregate as new snapshot rows. Returns rows loaded."""
    count = 0
    for _, row in aggregated.iterrows():
        snapshot = VendorPerformanceSnapshot(
            pipeline_run_id=pipeline_run_id,
            vendor_id=int(row["vendor_id"]),
            snapshot_date=datetime.utcnow(),
            total_revenue=float(row["total_revenue"]),
            total_orders=int(row["total_orders"]),
            avg_order_value=float(row["avg_order_value"]),
            units_sold=int(row["units_sold"]),
        )
        db.add(snapshot)
        count += 1
    db.commit()
    return count


def run_pipeline(db: Session, triggered_by: str = "manual") -> dict:
    """
    Orchestrates extract -> clean_transform -> aggregate -> load, wrapped in
    a PipelineRun audit record so every execution (manual or scheduled) is
    inspectable afterwards via GET /api/v1/etl/runs.
    """
    run = PipelineRun(
        pipeline_name="core_etl",
        triggered_by=triggered_by,
        status=PipelineStatus.RUNNING,
        started_at=datetime.utcnow(),
    )
    db.add(run)
    db.commit()
    db.refresh(run)

    try:
        raw = extract(db)
        cleaned = clean_transform(raw)
        aggregated = aggregate(cleaned)
        rows_loaded = load(db, aggregated, run.id)

        run.status = PipelineStatus.SUCCESS
        run.finished_at = datetime.utcnow()
        run.rows_extracted = len(raw)
        run.rows_loaded = rows_loaded
        run.summary = {
            "vendors_aggregated": int(aggregated.shape[0]),
            "total_revenue": float(aggregated["total_revenue"].sum()) if not aggregated.empty else 0.0,
        }
        db.commit()
        return {
            "run_id": run.id,
            "status": run.status.value,
            "rows_extracted": run.rows_extracted,
            "rows_loaded": run.rows_loaded,
            "summary": run.summary,
        }
    except Exception as exc:
        db.rollback()
        run.status = PipelineStatus.FAILED
        run.finished_at = datetime.utcnow()
        run.error_message = str(exc)
        db.add(run)
        db.commit()
        raise
