"""
Transaction model — one row per line-item sale. This is the raw fact table
that the sales aggregation engine (app/services/analytics_service.py) rolls
up into revenue-by-vendor, revenue-by-category, and top-product reports.

`status` (TransactionStatus) is the analytics-facing financial state used
by every revenue/report/ETL calculation (completed/pending/cancelled/
refunded) and is intentionally left alone by the order-lifecycle fields
below so existing analytics keep working unchanged.

`order_status` (OrderStatus) is the customer-facing fulfillment lifecycle
(placed -> shipped -> delivered, or cancelled/returned) shown on the "My
Orders" screen. The two are kept in sync at the moments that matter
(cancel sets both order_status=CANCELLED and status=CANCELLED; return
sets order_status=RETURNED and status=REFUNDED) so revenue reports
automatically exclude cancelled/returned orders without any extra code.
"""
import enum
from datetime import datetime
from typing import Optional
from sqlalchemy import Integer, Float, String, DateTime, ForeignKey, Enum
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class TransactionStatus(str, enum.Enum):
    COMPLETED = "completed"
    PENDING = "pending"
    CANCELLED = "cancelled"
    REFUNDED = "refunded"


class PaymentMethod(str, enum.Enum):
    COD = "cod"
    UPI = "upi"
    NET_BANKING = "net_banking"


class OrderStatus(str, enum.Enum):
    """Customer-facing fulfillment lifecycle for one order line-item."""
    PLACED = "placed"
    SHIPPED = "shipped"
    DELIVERED = "delivered"
    CANCELLED = "cancelled"
    RETURNED = "returned"


class Transaction(Base):
    __tablename__ = "transactions"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    vendor_id: Mapped[int] = mapped_column(ForeignKey("vendors.id"), nullable=False)
    product_id: Mapped[int] = mapped_column(ForeignKey("products.id"), nullable=False)
    customer_id: Mapped[Optional[int]] = mapped_column(
    nullable=True)
    quantity: Mapped[int] = mapped_column(Integer, nullable=False)
    unit_price: Mapped[float] = mapped_column(Float, nullable=False)
    total_amount: Mapped[float] = mapped_column(Float, nullable=False)

    # Promotional campaign attribution — total_amount is already net of this
    # discount (i.e. what the customer actually paid); discount_amount is the
    # amount that was taken off, used by revenue-intelligence's GMV and
    # promotion-performance calculations.
    discount_amount: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    promotion_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("promotions.id"), nullable=True
    )

    payment_method: Mapped[PaymentMethod] = mapped_column(
        Enum(PaymentMethod), default=PaymentMethod.COD, nullable=False
    )

    status: Mapped[TransactionStatus] = mapped_column(
        Enum(TransactionStatus), default=TransactionStatus.COMPLETED, nullable=False
    )
    transaction_date: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, index=True)

    # --- Order lifecycle (real e-commerce-style tracking) ---
    order_ref: Mapped[Optional[str]] = mapped_column(String(50), nullable=True, index=True)
    order_status: Mapped[OrderStatus] = mapped_column(
        Enum(OrderStatus), default=OrderStatus.PLACED, nullable=False
    )
    # Every order is assumed to deliver within 2 days of being placed.
    expected_delivery_date: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    shipped_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    delivered_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    cancelled_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    cancellation_reason: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    returned_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    return_reason: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)

    vendor = relationship("Vendor", back_populates="transactions")
    product = relationship("Product", back_populates="transactions")
    promotion = relationship("Promotion", back_populates="transactions")

    def __repr__(self) -> str:
        return f"<Transaction id={self.id} product_id={self.product_id} total={self.total_amount}>"