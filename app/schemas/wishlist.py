from datetime import datetime
from typing import Optional

from pydantic import BaseModel


class WishlistItemResponse(BaseModel):
    id: int
    product_id: int
    product_name: str
    price: float
    image_url: Optional[str] = None
    vendor_id: int
    rating: Optional[float] = None
    rating_count: int = 0
    quantity_available: int = 0
    added_at: datetime