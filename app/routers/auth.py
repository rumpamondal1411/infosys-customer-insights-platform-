from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.database import get_db
from app.schemas.auth import LoginRequest, LoginResponse, ChangePassword
from app.services import auth_service

router = APIRouter(
    prefix="/auth",
    tags=["Authentication"]
)


@router.post("/login", response_model=LoginResponse)
def login(payload: LoginRequest, db: Session = Depends(get_db)):
    return auth_service.login_vendor(db, payload)


@router.post("/change-password")
def change_password(
    payload:ChangePassword,
    db: Session = Depends(get_db)
):
    return auth_service.change_password(db, payload)