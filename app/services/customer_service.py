from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.models.customer import Customer
from app.models.product import Product
from app.models.product_view import ProductView
from app.schemas.customer import CustomerRegister, CustomerLogin, CustomerAddressUpdate, CustomerNameUpdate


def register_customer(db: Session, payload: CustomerRegister) -> Customer:
    existing = db.query(Customer).filter(Customer.email == payload.email).first()
    if existing:
        raise HTTPException(status_code=400, detail="An account with this email already exists")

    customer = Customer(
        name=payload.name,
        email=payload.email,
        password=payload.password,  # plaintext, matching this codebase's existing vendor/admin auth style
    )
    db.add(customer)
    db.commit()
    db.refresh(customer)
    return customer


def login_customer(db: Session, payload: CustomerLogin) -> dict:
    customer = db.query(Customer).filter(Customer.email == payload.email).first()

    if customer is None:
        raise HTTPException(status_code=401, detail="Invalid Email")

    if customer.password != payload.password:
        raise HTTPException(status_code=401, detail="Invalid Password")

    return {
        "message": "Login Successful",
        "customer_id": customer.id,
        "name": customer.name,
    }


def get_customer(db: Session, customer_id: int) -> Customer:
    customer = db.query(Customer).filter(Customer.id == customer_id).first()
    if not customer:
        raise HTTPException(status_code=404, detail=f"Customer {customer_id} not found")
    return customer


def update_address(db: Session, customer_id: int, payload: CustomerAddressUpdate) -> Customer:
    customer = get_customer(db, customer_id)
    customer.address_line = payload.address_line
    customer.city = payload.city
    customer.state = payload.state
    customer.pincode = payload.pincode
    customer.phone = payload.phone
    db.commit()
    db.refresh(customer)
    return customer


def update_name(db: Session, customer_id: int, payload: CustomerNameUpdate) -> Customer:
    """Updates the customer's display name (profile page 'Edit' action). Email is left
    unchanged since it's the login identifier."""
    customer = get_customer(db, customer_id)
    name = payload.name.strip()
    if not name:
        raise HTTPException(status_code=400, detail="Name cannot be empty")
    customer.name = name
    db.commit()
    db.refresh(customer)
    return customer


def track_view(db: Session, customer_id: int, product_id: int) -> ProductView:
    """
    Records a "customer looked at this product" event. This is the raw
    browsing/engagement signal used by the Milestone 2 Customer Behaviour
    & Recommendation Analytics module (customer_analytics_service.py)
    alongside purchase history from Transaction.
    """
    customer = db.query(Customer).filter(Customer.id == customer_id).first()
    if not customer:
        raise HTTPException(status_code=404, detail=f"Customer {customer_id} not found")
    product = db.query(Product).filter(Product.id == product_id).first()
    if not product:
        raise HTTPException(status_code=404, detail=f"Product {product_id} not found")

    view = ProductView(customer_id=customer_id, product_id=product_id)
    db.add(view)
    db.commit()
    db.refresh(view)
    return view