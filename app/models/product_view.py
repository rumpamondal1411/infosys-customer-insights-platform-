"""
ProductView model — one row per "customer looked at this product" event.

This is the raw browsing/engagement signal that Milestone 2's Customer
Behaviour & Recommendation Analytics module (app/services/customer_analytics_service.py)
uses alongside Transaction history to build engagement metrics and
content-based recommendations. Purchases already live in Transaction; this
table captures interest that didn't (yet) convert into a sale.
"""
from datetime import datetime

from sqlalchemy import Integer, DateTime, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class ProductView(Base):
    __tablename__ = "product_views"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    customer_id: Mapped[int] = mapped_column(ForeignKey("customers.id"), nullable=False, index=True)
    product_id: Mapped[int] = mapped_column(ForeignKey("products.id"), nullable=False, index=True)
    viewed_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, index=True)

    product = relationship("Product")

    def __repr__(self) -> str:
        return f"<ProductView customer_id={self.customer_id} product_id={self.product_id}>"
