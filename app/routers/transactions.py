"""
Transactions API — records sales that feed the analytics engine.
"""
from typing import Optional, List

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.database import get_db
from app.schemas.transaction import TransactionCreate, TransactionResponse
from app.services import transaction_service

router = APIRouter(prefix="/transactions", tags=["Transactions"])


@router.post("", response_model=TransactionResponse, status_code=201)
def record_transaction(payload: TransactionCreate, db: Session = Depends(get_db)):
    return transaction_service.record_transaction(db, payload)


@router.get("", response_model=List[TransactionResponse])
def list_transactions(
    vendor_id: Optional[int] = None,
    product_id: Optional[int] = None,
    skip: int = 0,
    limit: int = 100,
    db: Session = Depends(get_db),
):
    return transaction_service.list_transactions(db, vendor_id, product_id, skip, limit)
