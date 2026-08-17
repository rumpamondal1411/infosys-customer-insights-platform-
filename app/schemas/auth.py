from pydantic import BaseModel, EmailStr


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class LoginResponse(BaseModel):
    message: str
    vendor_id: int
    business_name: str


class ChangePassword(BaseModel):
    vendor_id: int
    old_password: str
    new_password: str