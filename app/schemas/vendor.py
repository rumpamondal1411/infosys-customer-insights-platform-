from datetime import datetime
from typing import Optional

from pydantic import BaseModel, EmailStr, Field, ConfigDict

from app.models.vendor import VendorStatus, VerificationStatus


class VendorBase(BaseModel):
    business_name: str = Field(..., max_length=150)
    legal_entity_name: Optional[str] = None
    tax_id: Optional[str] = None
    primary_category: Optional[str] = None
    contact_person: str
    email: EmailStr
    phone: str
    address: Optional[str] = None
    country: Optional[str] = None
    commission_rate: float = Field(0.10, ge=0, le=1)


class VendorCreate(VendorBase):
    password: str = Field("default123", min_length=6)


class VendorLogin(BaseModel):
    email: EmailStr
    password: str


class VendorUpdate(BaseModel):
    business_name: Optional[str] = None
    legal_entity_name: Optional[str] = None
    primary_category: Optional[str] = None
    contact_person: Optional[str] = None
    phone: Optional[str] = None
    address: Optional[str] = None
    country: Optional[str] = None
    commission_rate: Optional[float] = Field(None, ge=0, le=1)


class VendorStatusUpdate(BaseModel):
    reason: Optional[str] = None


class VendorResponse(VendorBase):
    model_config = ConfigDict(from_attributes=True)

    id: int
    status: VendorStatus
    verification_status: VerificationStatus
    compliance_notes: Optional[str] = None
    onboarded_at: datetime
    approved_at: Optional[datetime] = None
    suspended_at: Optional[datetime] = None
    created_at: datetime
    updated_at: datetime


class VendorPerformanceSummary(BaseModel):
    vendor_id: int
    business_name: str
    total_revenue: float
    total_orders: int
    total_units_sold: int
    active_products: int
    average_order_value: float