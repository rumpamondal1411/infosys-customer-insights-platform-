"""
Inventory monitoring API — stock levels, restocking, and low-stock alerts.
"""
from typing import Optional, List

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.database import get_db
from app.schemas.inventory import InventoryUpdate, InventoryResponse, RestockRequest, LowStockAlert
from app.schemas.inventory_forecast import InventoryForecastResponse
from app.services import inventory_service, inventory_forecast_service

router = APIRouter(prefix="/inventory", tags=["Inventory Monitoring"])
@router.get("/vendor/{vendor_id}")
def vendor_inventory(vendor_id: int, db: Session = Depends(get_db)):
    return inventory_service.get_vendor_inventory(db, vendor_id)

@router.get("", response_model=List[InventoryResponse])
def list_inventory(
    vendor_id: int,
    db: Session = Depends(get_db)
):
    return inventory_service.list_inventory(db, vendor_id)


@router.get("/{product_id}", response_model=InventoryResponse)
def get_inventory(product_id: int, db: Session = Depends(get_db)):
    return inventory_service.get_inventory_by_product(db, product_id)


@router.put("/{product_id}", response_model=InventoryResponse)
def update_inventory(product_id: int, payload: InventoryUpdate, db: Session = Depends(get_db)):
    return inventory_service.update_inventory(db, product_id, payload)


@router.post("/{product_id}/restock", response_model=InventoryResponse)
def restock(product_id: int, payload: RestockRequest, db: Session = Depends(get_db)):
    """Add stock to a product (e.g. after a warehouse replenishment)."""
    return inventory_service.restock(db, product_id, payload.quantity)


@router.get("/alerts/low-stock", response_model=List[LowStockAlert])
def low_stock_alerts(vendor_id: Optional[int] = None, db: Session = Depends(get_db)):
    """Products at or below their reorder threshold, with suggested reorder quantities."""
    return inventory_service.get_low_stock_alerts(db, vendor_id)


# --------------------------------------------------- Forecasting (Milestone 2)

@router.get("/forecast/{product_id}", response_model=InventoryForecastResponse, status_code=201)
def forecast_inventory(
    product_id: int,
    days: int = Query(30, ge=1, le=180, description="Days of history to average over"),
    horizon_days: int = Query(7, ge=1, le=90, description="Days ahead to forecast"),
    db: Session = Depends(get_db),
):
    """
    Moving-average forecast, persisted as an InventoryForecast row (predicted
    stock, forecast date, confidence level) so it can later be checked
    against what actually sold — see /validation/forecast-accuracy.
    """
    return inventory_forecast_service.generate_and_save_forecast(db, product_id, days, horizon_days)


@router.get("/forecast/{product_id}/history", response_model=List[InventoryForecastResponse])
def forecast_history(product_id: int, limit: int = 50, db: Session = Depends(get_db)):
    """Every past forecast run saved for this product."""
    return inventory_forecast_service.list_forecasts(db, product_id, limit)

@router.post("/forecast/run-all")
def forecast_all_products(
    days: int = Query(30, ge=1, le=180),
    horizon_days: int = Query(7, ge=1, le=90),
    db: Session = Depends(get_db),
):
    """Generates and persists a forecast for every active product in one call."""
    return inventory_forecast_service.generate_forecasts_for_all_products(db, days, horizon_days)


@router.get("/forecast/latest/all", response_model=List[InventoryForecastResponse])
def latest_forecasts(limit: int = 100, db: Session = Depends(get_db)):
    """Most recent forecast run per product, across all products — feeds the dashboard table."""
    return inventory_forecast_service.list_forecasts(db, None, limit)