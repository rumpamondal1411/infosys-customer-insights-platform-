"""
Inventory service — stock adjustments and low-stock alert detection.
Forecasting (moving-average demand projection) lives in analytics_service.py
since it operates on historical transactions, not just current stock.
"""
from datetime import datetime
from typing import Optional, List

from sqlalchemy.orm import Session
from fastapi import HTTPException, status

from app.models.inventory import Inventory
from app.models.product import Product
from app.schemas.inventory import InventoryUpdate, LowStockAlert


def get_inventory_by_product(db: Session, product_id: int) -> Inventory:
    inv = db.query(Inventory).filter(Inventory.product_id == product_id).first()
    if not inv:
        raise HTTPException(status.HTTP_404_NOT_FOUND, f"No inventory record for product {product_id}")
    # InventoryResponse requires product_name, which isn't a column on Inventory
    # itself — attach it from the related Product so response serialization
    # doesn't fail (this was a pre-existing bug: GET /inventory/{id} returned
    # a 500 any time it was called directly, since the raw ORM row has no
    # product_name attribute).
    inv.product_name = inv.product.name if inv.product else None
    return inv


def update_inventory(db: Session, product_id: int, payload: InventoryUpdate) -> Inventory:
    inv = get_inventory_by_product(db, product_id)
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(inv, field, value)
    inv.updated_at = datetime.utcnow()
    db.commit()
    db.refresh(inv)
    return inv


def restock(db: Session, product_id: int, quantity: int) -> Inventory:
    inv = get_inventory_by_product(db, product_id)
    inv.quantity_available += quantity
    inv.last_restocked_at = datetime.utcnow()
    db.commit()
    db.refresh(inv)
    return inv


def deduct_stock(db: Session, product_id: int, quantity: int) -> Inventory:
    """Used when a sale is recorded, to keep stock levels consistent."""
    inv = get_inventory_by_product(db, product_id)
    if inv.quantity_available < quantity:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            f"Insufficient stock for product {product_id}: "
            f"available={inv.quantity_available}, requested={quantity}",
        )
    inv.quantity_available -= quantity
    db.commit()
    db.refresh(inv)
    return inv


def get_low_stock_alerts(db: Session, vendor_id: Optional[int] = None) -> List[LowStockAlert]:
    """
    Returns products whose available quantity has fallen at or below their
    reorder level, along with a suggested replenishment quantity.
    """
    query = (
        db.query(Inventory, Product)
        .join(Product, Inventory.product_id == Product.id)
        .filter(Inventory.quantity_available <= Inventory.reorder_level)
    )
    if vendor_id:
        query = query.filter(Product.vendor_id == vendor_id)

    alerts = []
    for inv, product in query.all():
        alerts.append(
            LowStockAlert(
                product_id=product.id,
                sku=product.sku,
                product_name=product.name,
                vendor_id=product.vendor_id,
                quantity_available=inv.quantity_available,
                reorder_level=inv.reorder_level,
                reorder_quantity=inv.reorder_quantity,
                suggested_action=(
                    f"Reorder {inv.reorder_quantity} units "
                    f"(current stock {inv.quantity_available} <= threshold {inv.reorder_level})"
                ),
            )
        )
    return alerts

def get_vendor_inventory(db: Session, vendor_id: int):

    results = (
        db.query(Inventory, Product)
        .join(Product, Inventory.product_id == Product.id)
        .filter(Product.vendor_id == vendor_id)
        .all()
    )

    inventory_list = []

    for inv, product in results:

        inventory_list.append({

            "product_id": product.id,
            "product_name": product.name,
            "quantity_available": inv.quantity_available,
            "warehouse_location": inv.warehouse_location,
            "reorder_level": inv.reorder_level

        })

    return inventory_list

def list_inventory(db: Session, vendor_id: int):

    records = (
        db.query(Inventory, Product)
        .join(Product, Inventory.product_id == Product.id)
        .filter(Product.vendor_id == vendor_id)
        .all()
    )

    inventory = []

    for inv, product in records:
        inventory.append(
            {
                "id": inv.id,
                "product_id": inv.product_id,
                "product_name": product.name,
                "warehouse_location": inv.warehouse_location,
                "quantity_available": inv.quantity_available,
                "quantity_reserved": inv.quantity_reserved,
                "reorder_level": inv.reorder_level,
                "reorder_quantity": inv.reorder_quantity,
                "last_restocked_at": inv.last_restocked_at,
                "updated_at": inv.updated_at,
            }
        )

    return inventory