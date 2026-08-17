from typing import List


from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.database import get_db
from app.schemas.customer import (
    CustomerRegister, CustomerLogin, CustomerResponse, CustomerLoginResponse,
    CustomerAddressUpdate, CustomerNameUpdate,
)
from app.schemas.order import CheckoutRequest, CheckoutResponse, CancelOrderRequest, ReturnOrderRequest
from app.schemas.transaction import TransactionResponse
from app.schemas.wishlist import WishlistItemResponse
from app.services import customer_service, order_service, wishlist_service, rating_service

router = APIRouter(
    prefix="/customer",
    tags=["Customer"]
)


@router.post("/register", response_model=CustomerResponse, status_code=201)
def register(payload: CustomerRegister, db: Session = Depends(get_db)):
    return customer_service.register_customer(db, payload)


@router.post("/login", response_model=CustomerLoginResponse)
def login(payload: CustomerLogin, db: Session = Depends(get_db)):
    return customer_service.login_customer(db, payload)


@router.get("/{customer_id}", response_model=CustomerResponse)
def get_customer(customer_id: int, db: Session = Depends(get_db)):
    """Customer profile, including saved address — used to prefill the address form."""
    return customer_service.get_customer(db, customer_id)


@router.put("/{customer_id}/address", response_model=CustomerResponse)
def update_address(customer_id: int, payload: CustomerAddressUpdate, db: Session = Depends(get_db)):
    """Saves/updates the customer's single delivery address."""
    return customer_service.update_address(db, customer_id, payload)


@router.put("/{customer_id}/profile", response_model=CustomerResponse)
def update_profile(customer_id: int, payload: CustomerNameUpdate, db: Session = Depends(get_db)):
    """Updates the customer's display name from the profile page."""
    return customer_service.update_name(db, customer_id, payload)


@router.post("/checkout", response_model=CheckoutResponse, status_code=201)
def checkout(payload: CheckoutRequest, db: Session = Depends(get_db)):
    """Buy Now / cart checkout — creates one Transaction per cart line-item. Requires a saved delivery address."""
    return order_service.checkout(db, payload)


@router.get("/{customer_id}/orders", response_model=List[TransactionResponse])
def my_orders(customer_id: int, db: Session = Depends(get_db)):
    """Order history for a customer (used by the 'My Orders' view), with live-synced fulfillment status."""
    return order_service.list_customer_orders(db, customer_id)


@router.post("/{customer_id}/orders/{transaction_id}/cancel", response_model=TransactionResponse)
def cancel_order(customer_id: int, transaction_id: int, payload: CancelOrderRequest, db: Session = Depends(get_db)):
    """Cancel an order any time before it has been delivered."""
    return order_service.cancel_order(db, customer_id, transaction_id, payload.reason)


@router.post("/{customer_id}/orders/{transaction_id}/return", response_model=TransactionResponse)
def return_order(customer_id: int, transaction_id: int, payload: ReturnOrderRequest, db: Session = Depends(get_db)):
    """Return an order any time after it has been delivered."""
    return order_service.return_order(db, customer_id, transaction_id, payload.reason)


@router.post("/{customer_id}/track-view/{product_id}", status_code=201)
def track_view(customer_id: int, product_id: int, db: Session = Depends(get_db)):
    """Logs a product-view engagement event for recommendation analytics."""
    customer_service.track_view(db, customer_id, product_id)
    return {"tracked": True}


@router.get("/{customer_id}/wishlist", response_model=List[WishlistItemResponse])
def get_wishlist(customer_id: int, db: Session = Depends(get_db)):
    return wishlist_service.list_wishlist(db, customer_id)


@router.post("/{customer_id}/wishlist/{product_id}", status_code=201)
def add_to_wishlist(customer_id: int, product_id: int, db: Session = Depends(get_db)):
    wishlist_service.add_to_wishlist(db, customer_id, product_id)
    return {"added": True}


@router.delete("/{customer_id}/wishlist/{product_id}", status_code=204)
def remove_from_wishlist(customer_id: int, product_id: int, db: Session = Depends(get_db)):
    wishlist_service.remove_from_wishlist(db, customer_id, product_id)


@router.get("/{customer_id}/ratings")
def get_my_ratings(customer_id: int, db: Session = Depends(get_db)):
    """A customer's own review history ('My Reviews' on the profile page)."""
    return rating_service.list_ratings_by_customer(db, customer_id)


