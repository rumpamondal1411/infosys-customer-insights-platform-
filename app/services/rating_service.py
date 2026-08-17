"""
Rating service — lets a customer rate a product (1-5 stars, optional
short review) and keeps Product.rating / Product.rating_count (the
aggregate shown on every product card) in sync.

Design: rating again just updates your existing rating for that product
(upsert on customer_id+product_id) rather than creating a second row —
so "everyone's rating" always reflects one vote per customer, and the
average recalculates immediately after every submit.
"""
from fastapi import HTTPException, status
from sqlalchemy.orm import Session
from sqlalchemy import func

from app.models.rating import Rating
from app.models.product import Product
from app.models.customer import Customer


def _recompute_product_aggregate(db: Session, product_id: int) -> Product:
    product = db.query(Product).filter(Product.id == product_id).first()
    if not product:
        return product

    avg_stars, count = (
        db.query(func.avg(Rating.stars), func.count(Rating.id))
        .filter(Rating.product_id == product_id)
        .one()
    )
    product.rating = round(float(avg_stars), 1) if count else None
    product.rating_count = count or 0
    db.commit()
    db.refresh(product)
    return product


def submit_rating(db: Session, product_id: int, customer_id: int, stars: int, review_text: str | None = None) -> dict:
    if not db.query(Customer).filter(Customer.id == customer_id).first():
        raise HTTPException(status.HTTP_404_NOT_FOUND, f"Customer {customer_id} not found")
    if not db.query(Product).filter(Product.id == product_id).first():
        raise HTTPException(status.HTTP_404_NOT_FOUND, f"Product {product_id} not found")
    if not (1 <= stars <= 5):
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Rating must be between 1 and 5 stars")

    existing = (
        db.query(Rating)
        .filter(Rating.customer_id == customer_id, Rating.product_id == product_id)
        .first()
    )
    if existing:
        existing.stars = stars
        existing.review_text = review_text
    else:
        db.add(Rating(customer_id=customer_id, product_id=product_id, stars=stars, review_text=review_text))
    db.commit()

    product = _recompute_product_aggregate(db, product_id)

    return {
        "product_id": product_id,
        "rating": product.rating,
        "rating_count": product.rating_count,
        "your_rating": stars,
    }


def get_customer_rating(db: Session, product_id: int, customer_id: int) -> Rating | None:
    return (
        db.query(Rating)
        .filter(Rating.customer_id == customer_id, Rating.product_id == product_id)
        .first()
    )


def list_ratings_for_product(db: Session, product_id: int) -> list[dict]:
    rows = (
        db.query(Rating, Customer)
        .join(Customer, Rating.customer_id == Customer.id)
        .filter(Rating.product_id == product_id)
        .order_by(Rating.updated_at.desc())
        .all()
    )
    return [
        {
            "customer_name": customer.name,
            "stars": r.stars,
            "review_text": r.review_text,
            "updated_at": r.updated_at,
        }
        for r, customer in rows
    ]


def list_ratings_by_customer(db: Session, customer_id: int) -> list[dict]:
    """A customer's own review history ('My Reviews' on the profile page)."""
    rows = (
        db.query(Rating, Product)
        .join(Product, Rating.product_id == Product.id)
        .filter(Rating.customer_id == customer_id)
        .order_by(Rating.updated_at.desc())
        .all()
    )
    return [
        {
            "product_id": product.id,
            "product_name": product.name,
            "image_url": product.image_url,
            "stars": r.stars,
            "review_text": r.review_text,
            "updated_at": r.updated_at,
        }
        for r, product in rows
    ]