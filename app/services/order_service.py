"""
Order/checkout service — powers the customer-facing "Buy" flow (the
Flipkart/Meesho-style add-to-cart + checkout on /customer-dashboard), plus
the full post-purchase order lifecycle: placed -> shipped -> delivered
(every order is assumed to deliver within 2 days of being placed), with
cancellation allowed any time before delivery and returns allowed any time
after delivery.

Design note: this codebase has no separate Order table (Milestone 1 kept
Transaction as the single fact table analytics is built on). Rather than
add a parallel Order entity that would need to be kept in sync with
Transaction everywhere, a checkout simply creates one Transaction row per
cart line-item — each stamped with a shared `order_ref` (a UUID) so the
frontend can still group and display them together as "one order". This
keeps every existing analytics/report pipeline (which reads Transaction)
automatically aware of customer purchases with zero changes.
"""
import uuid
from datetime import datetime, timedelta
from typing import List, Optional

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.models.transaction import Transaction, TransactionStatus, OrderStatus
from app.models.product import Product, ProductStatus
from app.models.customer import Customer
from app.schemas.customer import has_complete_address
from app.schemas.order import CheckoutRequest
from app.services import inventory_service, promotion_service

# Every order is assumed to deliver within this many days of being placed.
DELIVERY_WINDOW_DAYS = 2

ADDRESS_REQUIRED_DETAIL = (
    "ADDRESS_REQUIRED: Please add your delivery address before placing an order."
)


def checkout(db: Session, payload: CheckoutRequest) -> dict:
    if not payload.items:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Cart is empty")

    customer = db.query(Customer).filter(Customer.id == payload.customer_id).first()
    if not customer:
        raise HTTPException(status.HTTP_404_NOT_FOUND, f"Customer {payload.customer_id} not found")

    # A delivery address is mandatory before any order can be placed — no
    # address means nowhere to ship the order, so this is checked before
    # anything else (stock, promo, etc.) is even validated.
    if not has_complete_address(customer):
        raise HTTPException(status.HTTP_400_BAD_REQUEST, ADDRESS_REQUIRED_DETAIL)

    # Merge duplicate product_ids in the cart into a single line
    merged: dict[int, int] = {}
    for item in payload.items:
        merged[item.product_id] = merged.get(item.product_id, 0) + item.quantity

    promo = promotion_service.get_active_promotion_by_code(db, payload.promotion_code) \
        if payload.promotion_code else None

    # Validate everything up front so checkout is all-or-nothing
    products_by_id: dict[int, Product] = {}
    for product_id, quantity in merged.items():
        product = db.query(Product).filter(Product.id == product_id).first()
        if not product:
            raise HTTPException(status.HTTP_404_NOT_FOUND, f"Product {product_id} not found")
        if product.status != ProductStatus.ACTIVE:
            raise HTTPException(status.HTTP_400_BAD_REQUEST, f"'{product.name}' is not available for purchase")
        inv = product.inventory
        if not inv or inv.quantity_available < quantity:
            available = inv.quantity_available if inv else 0
            raise HTTPException(
                status.HTTP_400_BAD_REQUEST,
                f"Insufficient stock for '{product.name}': available={available}, requested={quantity}"
                if available > 0 else f"'{product.name}' is out of stock",
            )
        products_by_id[product_id] = product

    order_ref = f"ORD-{uuid.uuid4().hex[:10].upper()}"
    placed_at = datetime.utcnow()
    expected_delivery_date = placed_at + timedelta(days=DELIVERY_WINDOW_DAYS)
    line_results = []
    subtotal = 0.0
    total_discount = 0.0

    for product_id, quantity in merged.items():
        product = products_by_id[product_id]
        line_total = round(product.price * quantity, 2)
        discount = promotion_service.compute_discount(promo, line_total)
        net_total = round(line_total - discount, 2)

        transaction = Transaction(
            vendor_id=product.vendor_id,
            product_id=product.id,
            customer_id=customer.id,
            quantity=quantity,
            unit_price=product.price,
            total_amount=net_total,
            discount_amount=discount,
            promotion_id=promo.id if promo else None,
            payment_method=payload.payment_method,
            status=TransactionStatus.COMPLETED,
            transaction_date=placed_at,
            order_ref=order_ref,
            order_status=OrderStatus.PLACED,
            expected_delivery_date=expected_delivery_date,
        )
        db.add(transaction)
        inventory_service.deduct_stock(db, product_id, quantity)

        db.flush()
        line_results.append({
            "transaction_id": transaction.id,
            "product_id": product.id,
            "product_name": product.name,
            "vendor_id": product.vendor_id,
            "quantity": quantity,
            "unit_price": product.price,
            "discount_amount": discount,
            "total_amount": net_total,
        })
        subtotal += line_total
        total_discount += discount

    db.commit()

    return {
        "order_ref": order_ref,
        "customer_id": customer.id,
        "placed_at": placed_at,
        "payment_method": payload.payment_method,
        "expected_delivery_date": expected_delivery_date,
        "items": line_results,
        "subtotal": round(subtotal, 2),
        "total_discount": round(total_discount, 2),
        "grand_total": round(subtotal - total_discount, 2),
    }


def _sync_order_status(db: Session, transaction: Transaction, now: Optional[datetime] = None) -> Transaction:
    """
    Advances an order's lifecycle purely based on elapsed time — no
    scheduled job is required for this to work. A "real" e-commerce
    platform would flip these via warehouse/carrier webhooks; here, since
    every order is assumed to deliver within DELIVERY_WINDOW_DAYS, we treat
    the halfway point as "shipped" and the full window as "delivered".

    Terminal states (cancelled/returned) are never touched. Delivered is
    also terminal for this function — once set, it's never re-derived.
    """
    if transaction.order_status in (OrderStatus.CANCELLED, OrderStatus.RETURNED, OrderStatus.DELIVERED):
        return transaction
    if not transaction.expected_delivery_date:
        return transaction

    now = now or datetime.utcnow()
    placed_at = transaction.transaction_date
    shipped_at = placed_at + (transaction.expected_delivery_date - placed_at) / 2

    changed = False
    if now >= transaction.expected_delivery_date:
        transaction.order_status = OrderStatus.DELIVERED
        transaction.delivered_at = transaction.expected_delivery_date
        if not transaction.shipped_at:
            transaction.shipped_at = shipped_at
        changed = True
    elif now >= shipped_at and transaction.order_status == OrderStatus.PLACED:
        transaction.order_status = OrderStatus.SHIPPED
        transaction.shipped_at = shipped_at
        changed = True

    if changed:
        db.commit()
        db.refresh(transaction)
    return transaction


def list_customer_orders(db: Session, customer_id: int) -> List[Transaction]:
    orders = (
        db.query(Transaction)
        .filter(Transaction.customer_id == customer_id)
        .order_by(Transaction.transaction_date.desc())
        .all()
    )
    # Bring every order's lifecycle status up to date before returning it,
    # so "My Orders" always reflects the real elapsed-time state.
    return [_sync_order_status(db, order) for order in orders]


def _get_customer_order(db: Session, customer_id: int, transaction_id: int) -> Transaction:
    transaction = (
        db.query(Transaction)
        .filter(Transaction.id == transaction_id, Transaction.customer_id == customer_id)
        .first()
    )
    if not transaction:
        raise HTTPException(status.HTTP_404_NOT_FOUND, f"Order {transaction_id} not found for this customer")
    return transaction


def cancel_order(db: Session, customer_id: int, transaction_id: int, reason: Optional[str] = None) -> Transaction:
    """Cancel an order any time before it has been delivered; restocks inventory."""
    transaction = _get_customer_order(db, customer_id, transaction_id)
    transaction = _sync_order_status(db, transaction)

    if transaction.order_status in (OrderStatus.CANCELLED, OrderStatus.RETURNED):
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "This order has already been cancelled or returned.")
    if transaction.order_status == OrderStatus.DELIVERED:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            "This order has already been delivered and can no longer be cancelled — you can return it instead.",
        )

    transaction.order_status = OrderStatus.CANCELLED
    transaction.cancelled_at = datetime.utcnow()
    transaction.cancellation_reason = reason
    transaction.status = TransactionStatus.CANCELLED

    inventory_service.restock(db, transaction.product_id, transaction.quantity)

    db.commit()
    db.refresh(transaction)
    return transaction


def return_order(db: Session, customer_id: int, transaction_id: int, reason: Optional[str] = None) -> Transaction:
    """Return an order any time after it has been delivered; restocks inventory and refunds."""
    transaction = _get_customer_order(db, customer_id, transaction_id)
    transaction = _sync_order_status(db, transaction)

    if transaction.order_status != OrderStatus.DELIVERED:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            "Only delivered orders can be returned.",
        )

    transaction.order_status = OrderStatus.RETURNED
    transaction.returned_at = datetime.utcnow()
    transaction.return_reason = reason
    transaction.status = TransactionStatus.REFUNDED

    inventory_service.restock(db, transaction.product_id, transaction.quantity)

    db.commit()
    db.refresh(transaction)
    return transaction