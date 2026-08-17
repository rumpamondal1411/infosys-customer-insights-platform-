"""
Milestone 2 — Inventory Tracking & Forecasting, with persistence.

This is the relational equivalent of the mentor-provided
controllers/inventoryController.js: forecastInventory() there computes a
moving-average forecast from recent transactions and *saves* it as an
InventoryForecast document. app/services/analytics_service.py already had
the moving-average math (Week 1); what was missing was persisting each
run, which is required so forecast accuracy can later be checked against
what actually happened (see app/services/validation_service.py).
"""
from datetime import datetime
from typing import List, Optional

import pandas as pd
from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.models.transaction import Transaction, TransactionStatus
from app.models.product import Product
from app.models.inventory_forecast import InventoryForecast


def _daily_sales_series(db: Session, product_id: int, days_history: int) -> pd.Series:
    rows = (
        db.query(Transaction.quantity, Transaction.transaction_date)
        .filter(Transaction.product_id == product_id)
        .filter(Transaction.status == TransactionStatus.COMPLETED)
        .all()
    )
    if not rows:
        return pd.Series(dtype=float)

    df = pd.DataFrame(rows, columns=["quantity", "transaction_date"])
    df["transaction_date"] = pd.to_datetime(df["transaction_date"])
    cutoff = df["transaction_date"].max() - pd.Timedelta(days=days_history)
    df = df[df["transaction_date"] >= cutoff]
    if df.empty:
        return pd.Series(dtype=float)

    daily = df.set_index("transaction_date").resample("D")["quantity"].sum()
    return daily


def _confidence_from_variability(daily: pd.Series) -> float:
    """
    Data-driven confidence in [0.3, 0.95]: more history and steadier daily
    sales (lower coefficient of variation) both push confidence up. Two
    data points is a floor case that always gets low confidence.
    """
    if daily.empty or daily.shape[0] < 3:
        return 0.3

    mean = daily.mean()
    std = daily.std(ddof=0)
    cv = (std / mean) if mean > 0 else 1.0  # coefficient of variation

    stability_score = 1 / (1 + cv)              # steadier sales -> closer to 1
    coverage_score = min(daily.shape[0] / 14.0, 1.0)  # more days of history -> closer to 1

    confidence = 0.3 + 0.65 * (0.6 * stability_score + 0.4 * coverage_score)
    return round(min(max(confidence, 0.3), 0.95), 2)


def generate_forecast(db: Session, product_id: int, days_history: int = 30, horizon_days: int = 7) -> dict:
    """Moving-average forecast (no persistence) — used by /analytics/forecast for a quick read."""
    product = db.query(Product).filter(Product.id == product_id).first()
    if not product:
        raise HTTPException(status.HTTP_404_NOT_FOUND, f"Product {product_id} not found")

    daily = _daily_sales_series(db, product_id, days_history)
    if daily.empty:
        return {
            "product_id": product_id, "avg_daily_units": 0.0,
            "predicted_stock": 0.0, "horizon_days": horizon_days,
            "confidence_level": 0.3, "data_points": 0,
        }

    avg_daily = float(daily.mean())
    confidence = _confidence_from_variability(daily)

    return {
        "product_id": product_id,
        "avg_daily_units": round(avg_daily, 2),
        "predicted_stock": round(avg_daily * horizon_days, 2),
        "horizon_days": horizon_days,
        "confidence_level": confidence,
        "data_points": int(daily.shape[0]),
    }


def generate_and_save_forecast(db: Session, product_id: int, days_history: int = 30,
                                horizon_days: int = 7) -> InventoryForecast:
    """Generates a forecast and persists it as an InventoryForecast row."""
    result = generate_forecast(db, product_id, days_history, horizon_days)

    forecast = InventoryForecast(
        product_id=product_id,
        predicted_stock=result["predicted_stock"],
        forecast_date=datetime.utcnow(),
        confidence_level=result["confidence_level"],
        horizon_days=horizon_days,
        method="moving_average",
    )
    db.add(forecast)
    db.commit()
    db.refresh(forecast)
    return forecast


def list_forecasts(db: Session, product_id: Optional[int] = None, limit: int = 100) -> List[InventoryForecast]:
    query = db.query(InventoryForecast)
    if product_id:
        query = query.filter(InventoryForecast.product_id == product_id)
    return query.order_by(InventoryForecast.forecast_date.desc()).limit(limit).all()

def generate_forecasts_for_all_products(db: Session, days_history: int = 30, horizon_days: int = 7) -> List[dict]:
    """
    Bulk-runs and persists a forecast for every active product — powers the
    'Forecast All' button on the admin Inventory Forecast dashboard so an
    admin doesn't have to enter product IDs one at a time.
    """
    from app.models.product import ProductStatus

    product_ids = [
        pid for (pid,) in db.query(Product.id).filter(Product.status == ProductStatus.ACTIVE).all()
    ]
    results = []
    for product_id in product_ids:
        forecast = generate_and_save_forecast(db, product_id, days_history, horizon_days)
        results.append({
            "product_id": forecast.product_id,
            "product_name": forecast.product.name if forecast.product else None,
            "predicted_stock": forecast.predicted_stock,
            "confidence_level": forecast.confidence_level,
            "horizon_days": forecast.horizon_days,
            "forecast_date": forecast.forecast_date,
        })
    return results