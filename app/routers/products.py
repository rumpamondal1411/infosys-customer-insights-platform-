"""
Product & Category Catalogue API — part of the Product & Inventory
Analytics Engine module.
"""
from typing import Optional, List

from fastapi import APIRouter, Depends, Query, UploadFile, File
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.product import ProductStatus
from app.schemas.product import ProductCreate, ProductUpdate, ProductResponse
from app.schemas.category import CategoryCreate, CategoryResponse
from app.services import product_service, rating_service

router = APIRouter(tags=["Product & Category Catalogue"])


# ---------------------------------------------------------------- Category

@router.post("/categories", response_model=CategoryResponse, status_code=201)
def create_category(payload: CategoryCreate, db: Session = Depends(get_db)):
    return product_service.create_category(db, payload)


@router.get("/categories", response_model=List[CategoryResponse])
def list_categories(db: Session = Depends(get_db)):
    return product_service.list_categories(db)


@router.get("/categories/{category_id}", response_model=CategoryResponse)
def get_category(category_id: int, db: Session = Depends(get_db)):
    return product_service.get_category(db, category_id)


# ----------------------------------------------------------------- Product

@router.post("/products", response_model=ProductResponse, status_code=201)
def create_product(payload: ProductCreate, db: Session = Depends(get_db)):
    """Add a product to the catalogue (vendor must be ACTIVE)."""
    return product_service.create_product(db, payload)


@router.get("/products", response_model=List[ProductResponse])
def list_products(
    vendor_id: Optional[int] = None,
    category_id: Optional[int] = None,
    status_filter: Optional[ProductStatus] = Query(None, alias="status"),
    search: Optional[str] = Query(None, description="Search by product name, description, or SKU"),
    skip: int = 0,
    limit: int = 100,
    db: Session = Depends(get_db),
):
    return product_service.list_products(db, vendor_id, category_id, status_filter, search, skip, limit)


@router.get("/products/{product_id}", response_model=ProductResponse)
def get_product(product_id: int, db: Session = Depends(get_db)):
    return product_service.get_product(db, product_id)


@router.put("/products/{product_id}", response_model=ProductResponse)
def update_product(product_id: int, payload: ProductUpdate, db: Session = Depends(get_db)):
    return product_service.update_product(db, product_id, payload)


@router.delete("/products/{product_id}", status_code=204)
def delete_product(product_id: int, db: Session = Depends(get_db)):
    product_service.delete_product(db, product_id)


@router.post("/products/{product_id}/image", response_model=ProductResponse)
async def upload_product_image(
    product_id: int, file: UploadFile = File(...), db: Session = Depends(get_db)
):
    """Upload or replace a product's image (JPG/PNG/WEBP, max 5MB)."""
    return await product_service.save_product_image(db, product_id, file)


@router.delete("/products/{product_id}/image", response_model=ProductResponse)
def delete_product_image(product_id: int, db: Session = Depends(get_db)):
    """Remove a product's image, reverting it to the placeholder."""
    return product_service.remove_product_image(db, product_id)


# ------------------------------------------------------------------ Ratings

class RatingSubmitRequest(BaseModel):
    customer_id: int
    stars: int
    review_text: Optional[str] = None


@router.post("/products/{product_id}/ratings")
def submit_product_rating(
    product_id: int,
    payload: RatingSubmitRequest,
    db: Session = Depends(get_db),
):
    """Submit or update a customer's rating/review for a product."""
    return rating_service.submit_rating(
        db,
        product_id=product_id,
        customer_id=payload.customer_id,
        stars=payload.stars,
        review_text=payload.review_text,
    )


@router.get("/products/{product_id}/ratings")
def get_product_ratings(product_id: int, db: Session = Depends(get_db)):
    """All ratings/reviews left on a product — used for a product detail page."""
    return rating_service.list_ratings_for_product(db, product_id)