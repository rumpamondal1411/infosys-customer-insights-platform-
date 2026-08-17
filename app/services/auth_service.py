from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.models.vendor import Vendor
from app.schemas.auth import LoginRequest


def login_vendor(db: Session, payload: LoginRequest):

    vendor = db.query(Vendor).filter(
        Vendor.email == payload.email
    ).first()

    if vendor is None:
        raise HTTPException(status_code=401, detail="Invalid Email")

    if vendor.password != payload.password:
        raise HTTPException(status_code=401, detail="Invalid Password")

    return {
        "message": "Login Successful",
        "vendor_id": vendor.id,
        "business_name": vendor.business_name
    }

def change_password(db, payload):

    vendor = db.query(Vendor).filter(
        Vendor.id == payload.vendor_id
    ).first()

    if not vendor:
        raise HTTPException(
            status_code=404,
            detail="Vendor not found"
        )

    if vendor.password != payload.old_password:
        raise HTTPException(
            status_code=400,
            detail="Old password is incorrect"
        )

    vendor.password = payload.new_password

    db.commit()

    return {
        "message": "Password changed successfully"
    }