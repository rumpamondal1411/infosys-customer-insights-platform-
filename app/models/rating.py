"""
Rating model — stores each customer's individual star rating (and optional
review text) for a product. The aggregate `rating` / `rating_count` columns
on Product are kept in sync from this table by rating_service.py whenever a
rating is submitted or updated.
"""
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class Rating(Base):
    __tablename__ = "ratings"
    __table_args__ = (
        UniqueConstraint("customer_id", "product_id", name="uq_rating_customer_product"),
    )

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    customer_id: Mapped[int] = mapped_column(ForeignKey("customers.id"), nullable=False, index=True)
    product_id: Mapped[int] = mapped_column(ForeignKey("products.id"), nullable=False, index=True)

    stars: Mapped[int] = mapped_column(Integer, nullable=False)  # 1-5
    review_text: Mapped[str] = mapped_column(String(1000), nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow
    )

    product = relationship("Product")
    customer = relationship("Customer")

    def __repr__(self) -> str:
        return f"<Rating customer_id={self.customer_id} product_id={self.product_id} stars={self.stars}>"