from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field, ConfigDict

from app.models.transaction import TransactionStatus, PaymentMethod, OrderStatus


class TransactionCreate(BaseModel):
    vendor_id: int
    product_id: int
    # Customer is optional for Week 1
    customer_id: Optional[int] = None
    quantity: int = Field(..., gt=0)
    unit_price: Optional[float] = None  # if omitted, taken from the product's current price
    discount_amount: float = 0.0
    promotion_id: Optional[int] = None
    payment_method: PaymentMethod = PaymentMethod.COD
    status: TransactionStatus = TransactionStatus.COMPLETED
    transaction_date: Optional[datetime] = None


class TransactionResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    vendor_id: int
    product_id: int
    customer_id: Optional[int] = None
    quantity: int
    unit_price: float
    total_amount: float
    discount_amount: float = 0.0
    promotion_id: Optional[int] = None
    payment_method: PaymentMethod
    status: TransactionStatus
    transaction_date: datetime

    # --- Order lifecycle ---
    order_ref: Optional[str] = None
    order_status: OrderStatus = OrderStatus.PLACED
    expected_delivery_date: Optional[datetime] = None
    shipped_at: Optional[datetime] = None
    delivered_at: Optional[datetime] = None
    cancelled_at: Optional[datetime] = None
    cancellation_reason: Optional[str] = None
    returned_at: Optional[datetime] = None
    return_reason: Optional[str] = None