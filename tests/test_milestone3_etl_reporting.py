"""
Milestone 3 tests — ETL pipeline, marketplace benchmarking, and report
export. ML/MLflow training is exercised separately (it's slower and needs
sklearn/mlflow installed) — see test_ml_segmentation.py.
"""
import os
from app.etl.pipeline import run_pipeline, extract, clean_transform, aggregate
from app.services import revenue_intelligence_service, report_service


def test_etl_pipeline_runs_end_to_end(db_session):
    result = run_pipeline(db_session, triggered_by="test")
    assert result["status"] == "success"
    assert result["rows_extracted"] >= 0
    assert "vendors_aggregated" in result["summary"]


def test_clean_transform_drops_invalid_rows():
    import pandas as pd
    df = pd.DataFrame([
        {"id": 1, "vendor_id": 1, "product_id": 1, "customer_id": 1, "quantity": 2,
         "unit_price": 10.0, "total_amount": 20.0, "discount_amount": 0.0,
         "status": "completed", "transaction_date": "2026-01-01"},
        {"id": 2, "vendor_id": None, "product_id": 1, "customer_id": 1, "quantity": 1,
         "unit_price": 10.0, "total_amount": 10.0, "discount_amount": 0.0,
         "status": "completed", "transaction_date": "2026-01-01"},
        {"id": 3, "vendor_id": 1, "product_id": 1, "customer_id": 1, "quantity": -1,
         "unit_price": 10.0, "total_amount": -10.0, "discount_amount": 0.0,
         "status": "completed", "transaction_date": "2026-01-01"},
        {"id": 4, "vendor_id": 1, "product_id": 1, "customer_id": 1, "quantity": 1,
         "unit_price": 10.0, "total_amount": 10.0, "discount_amount": 0.0,
         "status": "pending", "transaction_date": "2026-01-01"},
    ])
    cleaned = clean_transform(df)
    assert len(cleaned) == 1
    assert cleaned.iloc[0]["id"] == 1


def test_marketplace_benchmark_shape(db_session):
    result = revenue_intelligence_service.marketplace_benchmark(db_session)
    if result:
        row = result[0]
        for key in ("vendor_id", "total_revenue", "revenue_percentile", "revenue_vs_marketplace_avg_pct"):
            assert key in row


def test_export_section_writes_file(db_session):
    path = report_service.export_section(db_session, "vendor_performance", "csv")
    assert os.path.exists(path)
    assert path.endswith(".csv")


def test_export_section_rejects_unknown_section(db_session):
    import pytest
    with pytest.raises(ValueError):
        report_service.export_section(db_session, "not_a_real_section", "csv")
