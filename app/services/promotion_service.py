"""
Promotion service — CRUD for promotional campaigns, and the discount
calculation used at checkout (transaction_service.py) and reported on by
revenue_intelligence_service.py.
"""
from datetime import datetime
from typing import Optional

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.models.promotion import Promotion, DiscountType
from app.schemas.promotion import PromotionCreate


def create_promotion(db: Session, payload: PromotionCreate) -> Promotion:
    existing = db.query(Promotion).filter(Promotion.code == payload.code.upper()).first()
    if existing:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, f"Promotion code '{payload.code}' already exists")

    promo = Promotion(
        code=payload.code.upper(),
        description=payload.description,
        discount_type=payload.discount_type,
        discount_value=payload.discount_value,
        start_date=payload.start_date or datetime.utcnow(),
        end_date=payload.end_date,
        active=payload.active,
    )
    db.add(promo)
    db.commit()
    db.refresh(promo)
    return promo


def list_promotions(db: Session):
    return db.query(Promotion).order_by(Promotion.id.desc()).all()


def get_active_promotion_by_code(db: Session, code: str) -> Optional[Promotion]:
    if not code:
        return None
    promo = db.query(Promotion).filter(Promotion.code == code.strip().upper()).first()
    if not promo or not promo.active:
        return None
    now = datetime.utcnow()
    if promo.start_date and now < promo.start_date:
        return None
    if promo.end_date and now > promo.end_date:
        return None
    return promo


def compute_discount(promo: Optional[Promotion], line_total: float) -> float:
    """Returns the discount amount (never more than the line total)."""
    if not promo:
        return 0.0
    if promo.discount_type == DiscountType.PERCENT:
        discount = line_total * (promo.discount_value / 100.0)
    else:
        discount = promo.discount_value
    return round(min(discount, line_total), 2)


def get_promotion_or_404(db: Session, promotion_id: int) -> Promotion:
    promo = db.query(Promotion).filter(Promotion.id == promotion_id).first()
    if not promo:
        raise HTTPException(status.HTTP_404_NOT_FOUND, f"Promotion {promotion_id} not found")
    return promo


def update_promotion(db: Session, promotion_id: int, payload: PromotionCreate) -> Promotion:
    promo = get_promotion_or_404(db, promotion_id)
    new_code = payload.code.strip().upper()
    if new_code != promo.code:
        clash = db.query(Promotion).filter(Promotion.code == new_code, Promotion.id != promotion_id).first()
        if clash:
            raise HTTPException(status.HTTP_400_BAD_REQUEST, f"Promotion code '{payload.code}' already exists")
    promo.code = new_code
    promo.description = payload.description
    promo.discount_type = payload.discount_type
    promo.discount_value = payload.discount_value
    promo.start_date = payload.start_date or promo.start_date
    promo.end_date = payload.end_date
    promo.active = payload.active
    db.commit()
    db.refresh(promo)
    return promo


def delete_promotion(db: Session, promotion_id: int) -> None:
    """
    Deletes a promotion. Any past transaction that already used this code
    keeps its saved discount_amount (that historical number doesn't
    change), but its promotion_id link is cleared so revenue-intelligence
    reporting doesn't break on a dangling foreign key.
    """
    from app.models.transaction import Transaction

    promo = get_promotion_or_404(db, promotion_id)
    db.query(Transaction).filter(Transaction.promotion_id == promotion_id).update(
        {Transaction.promotion_id: None}
    )
    db.delete(promo)
    db.commit()