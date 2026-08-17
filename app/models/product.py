"""
Product model — centralized product catalogue shared across vendors,
categories, pricing, and (via relationship) inventory records.
"""
import enum
from datetime import datetime
from typing import Optional

from sqlalchemy import String, Float, Integer, ForeignKey, DateTime, Enum, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class ProductStatus(str, enum.Enum):
    DRAFT = "draft"
    ACTIVE = "active"
    INACTIVE = "inactive"
    DISCONTINUED = "discontinued"


class Product(Base):
    __tablename__ = "products"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    vendor_id: Mapped[int] = mapped_column(ForeignKey("vendors.id"), nullable=False)
    category_id: Mapped[int] = mapped_column(ForeignKey("categories.id"), nullable=True)

    sku: Mapped[str] = mapped_column(String(64), unique=True, nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(200), nullable=False, index=True)
    description: Mapped[str] = mapped_column(Text, nullable=True)
    image_url: Mapped[str] = mapped_column(String(255), nullable=True)

    price: Mapped[float] = mapped_column(Float, nullable=False)
    cost_price: Mapped[float] = mapped_column(Float, nullable=True)

    # Customer-facing rating shown on the product card (e.g. "4.3 ★ (128)").
    # There's no separate review/rating table in this codebase yet, so this
    # is a simple aggregate maintained directly on the product row.
    rating: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    rating_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    status: Mapped[ProductStatus] = mapped_column(
        Enum(ProductStatus), default=ProductStatus.ACTIVE, nullable=False
    )

    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow
    )

    vendor = relationship("Vendor", back_populates="products")
    category = relationship("Category", back_populates="products")
    inventory = relationship(
        "Inventory", back_populates="product", uselist=False, cascade="all, delete-orphan"
    )
    transactions = relationship("Transaction", back_populates="product")

    @property
    def quantity_available(self) -> int:
        """Live stock count — used by the customer dashboard to show 'Out of Stock'."""
        return self.inventory.quantity_available if self.inventory else 0

    @property
    def in_stock(self) -> bool:
        return self.quantity_available > 0

    def __repr__(self) -> str:
        return f"<Product id={self.id} sku={self.sku} name={self.name}>"






