from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.models.wishlist import Wishlist
from app.models.product import Product
from app.models.customer import Customer


def add_to_wishlist(db: Session, customer_id: int, product_id: int) -> Wishlist:
    if not db.query(Customer).filter(Customer.id == customer_id).first():
        raise HTTPException(status.HTTP_404_NOT_FOUND, f"Customer {customer_id} not found")
    if not db.query(Product).filter(Product.id == product_id).first():
        raise HTTPException(status.HTTP_404_NOT_FOUND, f"Product {product_id} not found")

    existing = db.query(Wishlist).filter(
        Wishlist.customer_id == customer_id, Wishlist.product_id == product_id
    ).first()
    if existing:
        return existing  # already saved — idempotent, not an error

    item = Wishlist(customer_id=customer_id, product_id=product_id)
    db.add(item)
    db.commit()
    db.refresh(item)
    return item


def remove_from_wishlist(db: Session, customer_id: int, product_id: int) -> None:
    item = db.query(Wishlist).filter(
        Wishlist.customer_id == customer_id, Wishlist.product_id == product_id
    ).first()
    if item:
        db.delete(item)
        db.commit()


def list_wishlist(db: Session, customer_id: int) -> list[dict]:
    rows = (
        db.query(Wishlist, Product)
        .join(Product, Wishlist.product_id == Product.id)
        .filter(Wishlist.customer_id == customer_id)
        .order_by(Wishlist.added_at.desc())
        .all()
    )
    return [
        {
            "id": w.id,
            "product_id": p.id,
            "product_name": p.name,
            "price": p.price,
            "image_url": p.image_url,
            "vendor_id": p.vendor_id,
            "rating": p.rating,
            "rating_count": p.rating_count,
            "quantity_available": p.quantity_available,
            "added_at": w.added_at,
        }
        for w, p in rows
    ]