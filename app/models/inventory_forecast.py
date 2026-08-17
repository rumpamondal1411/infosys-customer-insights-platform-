"""
InventoryForecast model — one row per forecast run for a product.

This is the relational equivalent of the mentor-provided
`models/inventoryForecast.js` (Mongoose) schema: rather than recomputing
a forecast on every request and throwing it away, each run is persisted
here (predicted_stock, forecast_date, confidence_level) so forecasts can
later be validated against what actually happened
(see app/services/validation_service.py).
"""
from datetime import datetime

from sqlalchemy import Integer, Float, DateTime, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class InventoryForecast(Base):
    __tablename__ = "inventory_forecasts"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    product_id: Mapped[int] = mapped_column(ForeignKey("products.id"), nullable=False, index=True)

    # Mirrors the mentor's schema fields
    predicted_stock: Mapped[float] = mapped_column(Float, nullable=False)
    forecast_date: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, index=True)
    confidence_level: Mapped[float] = mapped_column(Float, nullable=False)

    # Extra bookkeeping so a forecast run can be validated later against
    # what actually sold in the window it predicted for.
    horizon_days: Mapped[int] = mapped_column(Integer, default=7, nullable=False)
    method: Mapped[str] = mapped_column(String(50), default="moving_average", nullable=False)

    product = relationship("Product")

    def __repr__(self) -> str:
        return f"<InventoryForecast product_id={self.product_id} predicted={self.predicted_stock}>"
