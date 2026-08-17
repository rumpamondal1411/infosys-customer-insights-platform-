"""
Product & category service — catalogue management plus the inventory
record that gets created alongside every new product.
"""
from datetime import datetime
from pathlib import Path
from typing import Optional

from fastapi import HTTPException, status, UploadFile
from sqlalchemy.orm import Session

from app.models.product import Product, ProductStatus
from app.models.category import Category
from app.models.inventory import Inventory
from app.models.vendor import Vendor, VendorStatus
from app.schemas.product import ProductCreate, ProductUpdate
from app.schemas.category import CategoryCreate

# ------------------------------------------------------------ Product Images

UPLOAD_DIR = Path("app/static/uploads/products")
ALLOWED_IMAGE_TYPES = {
    "image/jpeg": ".jpg",
    "image/png": ".png",
    "image/webp": ".webp",
}
MAX_IMAGE_SIZE_BYTES = 5 * 1024 * 1024  # 5 MB


# ---------------------------------------------------------------- Category

def create_category(db: Session, payload: CategoryCreate) -> Category:
    category = Category(**payload.model_dump())
    db.add(category)
    db.commit()
    db.refresh(category)
    return category


def list_categories(db: Session):
    return db.query(Category).order_by(Category.id).all()


def get_category(db: Session, category_id: int) -> Category:
    category = db.query(Category).filter(Category.id == category_id).first()
    if not category:
        raise HTTPException(status.HTTP_404_NOT_FOUND, f"Category {category_id} not found")
    return category


# ----------------------------------------------------------------- Product

def create_product(db: Session, payload: ProductCreate) -> Product:
    vendor = db.query(Vendor).filter(Vendor.id == payload.vendor_id).first()
    if not vendor:
        raise HTTPException(status.HTTP_404_NOT_FOUND, f"Vendor {payload.vendor_id} not found")
    if vendor.status != VendorStatus.ACTIVE:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            "Only active (approved) vendors may add products to the catalogue",
        )

    existing_sku = db.query(Product).filter(Product.sku == payload.sku).first()
    if existing_sku:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, f"SKU '{payload.sku}' already exists")

    data = payload.model_dump(exclude={
        "initial_quantity", "warehouse_location", "reorder_level", "reorder_quantity"
    })
    product = Product(**data)
    db.add(product)
    db.flush()  # get product.id before creating inventory row

    inventory = Inventory(
        product_id=product.id,
        warehouse_location=payload.warehouse_location or "MAIN-WH",
        quantity_available=payload.initial_quantity or 0,
        reorder_level=payload.reorder_level or 10,
        reorder_quantity=payload.reorder_quantity or 50,
        last_restocked_at=datetime.utcnow() if (payload.initial_quantity or 0) > 0 else None,
    )
    db.add(inventory)
    db.commit()
    db.refresh(product)
    return product


def get_product(db: Session, product_id: int) -> Product:
    product = db.query(Product).filter(Product.id == product_id).first()
    if not product:
        raise HTTPException(status.HTTP_404_NOT_FOUND, f"Product {product_id} not found")
    return product


def list_products(
    db: Session,
    vendor_id: Optional[int] = None,
    category_id: Optional[int] = None,
    status_filter: Optional[ProductStatus] = None,
    search: Optional[str] = None,
    skip: int = 0,
    limit: int = 100,
):
    query = db.query(Product).outerjoin(Category)
    if vendor_id:
        query = query.filter(Product.vendor_id == vendor_id)
    if category_id:
        query = query.filter(Product.category_id == category_id)
    if status_filter:
        query = query.filter(Product.status == status_filter)
    if search:
        like = f"%{search.strip()}%"
        query = query.filter(
            Product.name.ilike(like) |
            Product.description.ilike(like) |
            Product.sku.ilike(like) |
            Category.name.ilike(like)
            )
    return query.order_by(Product.id).offset(skip).limit(limit).all()


def update_product(db: Session, product_id: int, payload: ProductUpdate) -> Product:
    product = get_product(db, product_id)
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(product, field, value)
    product.updated_at = datetime.utcnow()
    db.commit()
    db.refresh(product)
    return product


def delete_product(db: Session, product_id: int) -> None:
    product = get_product(db, product_id)
    db.delete(product)
    db.commit()


async def save_product_image(db: Session, product_id: int, file: UploadFile) -> Product:
    """
    Validates and stores a product image on local disk (under
    app/static/uploads/products/), then saves the resulting URL on the
    product row. Only the file path/URL lives in the database — the image
    bytes themselves are never stored in SQLite, which is the standard
    pattern regardless of which database engine is used.
    """
    product = get_product(db, product_id)

    if file.content_type not in ALLOWED_IMAGE_TYPES:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            "Only JPG, PNG, and WEBP images are allowed",
        )

    contents = await file.read()
    if len(contents) > MAX_IMAGE_SIZE_BYTES:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            "Image must be smaller than 5MB",
        )
    if len(contents) == 0:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Uploaded file is empty")

    UPLOAD_DIR.mkdir(parents=True, exist_ok=True)

    # Remove any previous image for this product (in case the extension changed)
    for existing in UPLOAD_DIR.glob(f"{product_id}.*"):
        existing.unlink(missing_ok=True)

    ext = ALLOWED_IMAGE_TYPES[file.content_type]
    filename = f"{product_id}{ext}"
    filepath = UPLOAD_DIR / filename
    with open(filepath, "wb") as f:
        f.write(contents)

    product.image_url = f"/static/uploads/products/{filename}"
    product.updated_at = datetime.utcnow()
    db.commit()
    db.refresh(product)
    return product


def remove_product_image(db: Session, product_id: int) -> Product:
    product = get_product(db, product_id)
    if product.image_url:
        filepath = Path("app" + product.image_url)  # image_url starts with /static/...
        if filepath.exists():
            filepath.unlink()
        product.image_url = None
        product.updated_at = datetime.utcnow()
        db.commit()
        db.refresh(product)
    return product
