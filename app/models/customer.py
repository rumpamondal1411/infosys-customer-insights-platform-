"""
Customer model.

Note: customer accounts are NOT part of Milestone 1's official scope
(vendor onboarding, product catalogue, inventory, sales aggregation).
This is a lightweight addition to support a separate customer login +
browse-products dashboard, kept intentionally simple to match the style
of the existing Vendor/Admin auth in this codebase.
"""
from datetime import datetime
from typing import Optional

from sqlalchemy import String, DateTime
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class Customer(Base):
    __tablename__ = "customers"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    email: Mapped[str] = mapped_column(String(120), unique=True, nullable=False, index=True)
    password: Mapped[str] = mapped_column(String(255), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    # Single saved delivery address per customer — kept simple (one address,
    # not a list of multiple addresses) to match the scope of the rest of
    # this dashboard. All optional so existing customers aren't broken.
    address_line: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    city: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    state: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    pincode: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)
    phone: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)

    def __repr__(self) -> str:
        return f"<Customer id={self.id} name={self.name}>"