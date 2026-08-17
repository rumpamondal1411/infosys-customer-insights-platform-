from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field, ConfigDict

from app.models.product import ProductStatus


class ProductBase(BaseModel):
    sku: str = Field(..., max_length=64)
    name: str = Field(..., max_length=200)
    description: Optional[str] = None
    category_id: Optional[int] = None
    price: float = Field(..., gt=0)
    cost_price: Optional[float] = Field(None, ge=0)


class ProductCreate(ProductBase):
    vendor_id: int
    # Optional initial stock so a product can be created with inventory in one call
    initial_quantity: Optional[int] = Field(0, ge=0)
    warehouse_location: Optional[str] = "MAIN-WH"
    reorder_level: Optional[int] = 10
    reorder_quantity: Optional[int] = 50


class ProductUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    category_id: Optional[int] = None
    price: Optional[float] = Field(None, gt=0)
    cost_price: Optional[float] = Field(None, ge=0)
    status: Optional[ProductStatus] = None


class ProductResponse(ProductBase):
    model_config = ConfigDict(from_attributes=True)

    id: int
    vendor_id: int
    status: ProductStatus
    image_url: Optional[str] = None
    rating: Optional[float] = None
    rating_count: int = 0
    quantity_available: int = 0
    created_at: datetime
    updated_at: datetime
