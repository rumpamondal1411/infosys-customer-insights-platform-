from datetime import datetime
from pydantic import BaseModel, ConfigDict


class InventoryForecastResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    product_id: int
    predicted_stock: float
    forecast_date: datetime
    confidence_level: float
    horizon_days: int
    method: str
