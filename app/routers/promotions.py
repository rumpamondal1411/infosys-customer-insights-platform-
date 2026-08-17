"""
Promotional Campaigns API — part of the Sales Analytics & Revenue
Intelligence module (Milestone 2). Lets an admin/vendor create discount
codes that customers apply at checkout (see order_service.checkout),
whose performance is then measured in revenue_intelligence_service.
"""
from typing import List

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.database import get_db
from app.schemas.promotion import PromotionCreate, PromotionResponse
from app.services import promotion_service

router = APIRouter(prefix="/promotions", tags=["Promotions"])


@router.post("", response_model=PromotionResponse, status_code=201)
def create_promotion(payload: PromotionCreate, db: Session = Depends(get_db)):
    return promotion_service.create_promotion(db, payload)


@router.get("", response_model=List[PromotionResponse])
def list_promotions(db: Session = Depends(get_db)):
    return promotion_service.list_promotions(db)


@router.put("/{promotion_id}", response_model=PromotionResponse)
def update_promotion(promotion_id: int, payload: PromotionCreate, db: Session = Depends(get_db)):
    return promotion_service.update_promotion(db, promotion_id, payload)


@router.delete("/{promotion_id}", status_code=204)
def delete_promotion(promotion_id: int, db: Session = Depends(get_db)):
    promotion_service.delete_promotion(db, promotion_id)