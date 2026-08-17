"""
Order/checkout schemas — the customer "Buy" flow.

There's no separate Order table in this schema (see design note in
app/services/order_service.py): a checkout produces one Transaction row
per cart line-item, tagged with a shared order_ref so they can still be
grouped and displayed together as "one order" on the frontend.
"""
from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel, Field, ConfigDict

from app.models.transaction import PaymentMethod


class CartItem(BaseModel):
    product_id: int
    quantity: int = Field(..., gt=0)


class CheckoutRequest(BaseModel):
    customer_id: int
    items: List[CartItem]
    promotion_code: Optional[str] = None
    payment_method: PaymentMethod = PaymentMethod.COD


class CancelOrderRequest(BaseModel):
    reason: Optional[str] = None


class ReturnOrderRequest(BaseModel):
    reason: Optional[str] = None


class OrderLineResult(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    transaction_id: int
    product_id: int
    product_name: str
    vendor_id: int
    quantity: int
    unit_price: float
    discount_amount: float
    total_amount: float


class CheckoutResponse(BaseModel):
    order_ref: str
    customer_id: int
    placed_at: datetime
    payment_method: PaymentMethod
    expected_delivery_date: datetime
    items: List[OrderLineResult]
    subtotal: float
    total_discount: float
    grand_total: float