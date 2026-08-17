"""
Transaction service — records a sale, resolves unit price from the product
catalogue if not supplied, and keeps inventory in sync.
"""
from datetime import datetime

from sqlalchemy.orm import Session
from fastapi import HTTPException, status

from app.models.transaction import Transaction, TransactionStatus
from app.models.product import Product
from app.schemas.transaction import TransactionCreate
from app.services import inventory_service


def record_transaction(db: Session, payload: TransactionCreate) -> Transaction:
    product = db.query(Product).filter(Product.id == payload.product_id).first()
    if not product:
        raise HTTPException(status.HTTP_404_NOT_FOUND, f"Product {payload.product_id} not found")
    if product.vendor_id != payload.vendor_id:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST, "Product does not belong to the given vendor"
        )

    unit_price = payload.unit_price if payload.unit_price is not None else product.price
    gross_amount = round(unit_price * payload.quantity, 2)
    discount_amount = round(payload.discount_amount or 0.0, 2)
    total_amount = round(max(gross_amount - discount_amount, 0.0), 2)

    transaction = Transaction(
        vendor_id=payload.vendor_id,
        product_id=payload.product_id,
        customer_id=payload.customer_id,
        quantity=payload.quantity,
        unit_price=unit_price,
        total_amount=total_amount,
        discount_amount=discount_amount,
        promotion_id=payload.promotion_id,
        payment_method=payload.payment_method,
        status=payload.status,
        transaction_date=payload.transaction_date or datetime.utcnow(),
    )
    db.add(transaction)

    # Keep inventory consistent for completed sales
    if payload.status == TransactionStatus.COMPLETED:
        inventory_service.deduct_stock(db, payload.product_id, payload.quantity)

    db.commit()
    db.refresh(transaction)
    return transaction


def list_transactions(db: Session, vendor_id: int = None, product_id: int = None,
                       skip: int = 0, limit: int = 100):
    query = db.query(Transaction)
    if vendor_id:
        query = query.filter(Transaction.vendor_id == vendor_id)
    if product_id:
        query = query.filter(Transaction.product_id == product_id)
    return query.order_by(Transaction.transaction_date.desc()).offset(skip).limit(limit).all()