from datetime import datetime
from typing import Optional

from pydantic import BaseModel, EmailStr, ConfigDict


class CustomerRegister(BaseModel):
    name: str
    email: EmailStr
    password: str


class CustomerLogin(BaseModel):
    email: EmailStr
    password: str


class CustomerLoginResponse(BaseModel):
    message: str
    customer_id: int
    name: str


class CustomerAddressUpdate(BaseModel):
    address_line: Optional[str] = None
    city: Optional[str] = None
    state: Optional[str] = None
    pincode: Optional[str] = None
    phone: Optional[str] = None


class CustomerNameUpdate(BaseModel):
    name: str


class CustomerResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    email: EmailStr
    created_at: datetime
    address_line: Optional[str] = None
    city: Optional[str] = None
    state: Optional[str] = None
    pincode: Optional[str] = None
    phone: Optional[str] = None


def has_complete_address(customer) -> bool:
    """
    A delivery address is considered complete once the fields actually
    needed to ship an order are present: the street line, city, pincode,
    and a contact phone number. State is nice-to-have but not required.
    """
    return bool(
        (customer.address_line or "").strip()
        and (customer.city or "").strip()
        and (customer.pincode or "").strip()
        and (customer.phone or "").strip()
    )