"""
Promotion model — a lightweight promotional-campaign record.

Milestone 2's Sales Analytics & Revenue Intelligence module is required to
aggregate transaction data "from marketplace orders, payments, refunds, AND
promotional campaigns". This model is the minimal schema needed to attach a
real discount to real transactions (see Transaction.promotion_id /
discount_amount) so campaign performance can be measured from actual sales
data rather than assumed.
"""
import enum
from datetime import datetime

from sqlalchemy import String, Float, DateTime, Enum, Boolean
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class DiscountType(str, enum.Enum):
    PERCENT = "percent"   # discount_value is a percentage, e.g. 15 = 15% off
    FLAT = "flat"         # discount_value is a flat currency amount off the line total


class Promotion(Base):
    __tablename__ = "promotions"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    code: Mapped[str] = mapped_column(String(30), unique=True, nullable=False, index=True)
    description: Mapped[str] = mapped_column(String(255), nullable=True)

    discount_type: Mapped[DiscountType] = mapped_column(
        Enum(DiscountType), default=DiscountType.PERCENT, nullable=False
    )
    discount_value: Mapped[float] = mapped_column(Float, nullable=False)

    start_date: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    end_date: Mapped[datetime] = mapped_column(DateTime, nullable=True)
    active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    transactions = relationship("Transaction", back_populates="promotion")

    def __repr__(self) -> str:
        return f"<Promotion code={self.code} {self.discount_value} {self.discount_type}>"
