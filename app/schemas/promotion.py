from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field, ConfigDict

from app.models.promotion import DiscountType


class PromotionCreate(BaseModel):
    code: str = Field(..., max_length=30)
    description: Optional[str] = None
    discount_type: DiscountType = DiscountType.PERCENT
    discount_value: float = Field(..., gt=0)
    start_date: Optional[datetime] = None
    end_date: Optional[datetime] = None
    active: bool = True


class PromotionResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    code: str
    description: Optional[str] = None
    discount_type: DiscountType
    discount_value: float
    start_date: datetime
    end_date: Optional[datetime] = None
    active: bool
