from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field, ConfigDict


class InventoryUpdate(BaseModel):
    quantity_available: Optional[int] = Field(None, ge=0)
    quantity_reserved: Optional[int] = Field(None, ge=0)
    reorder_level: Optional[int] = Field(None, ge=0)
    reorder_quantity: Optional[int] = Field(None, ge=0)
    warehouse_location: Optional[str] = None


class RestockRequest(BaseModel):
    quantity: int = Field(..., gt=0)


class InventoryResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    product_id: int
    product_name:str
    warehouse_location: str
    quantity_available: int
    quantity_reserved: int
    reorder_level: int
    reorder_quantity: int
    last_restocked_at: Optional[datetime] = None
    updated_at: datetime


class LowStockAlert(BaseModel):
    product_id: int
    sku: str
    product_name: str
    vendor_id: int
    quantity_available: int
    reorder_level: int
    reorder_quantity: int
    suggested_action: str
