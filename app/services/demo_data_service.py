"""
Additive demo-data helper — adds fake customers (with purchase history and
browsing activity against the marketplace's EXISTING products) without
touching or deleting any existing vendors, products, or data. Meant for
quickly populating segmentation/recommendation/churn/validation dashboards
on a live database that already has real vendors/products you don't want
to lose (unlike app/utils/seed_data.py, which builds the whole catalogue
from scratch).
"""
import random
from datetime import datetime, timedelta

from faker import Faker
from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.models.customer import Customer
from app.models.product import Product, ProductStatus
from app.models.transaction import Transaction, TransactionStatus, OrderStatus
from app.models.product_view import ProductView

fake = Faker()


def add_demo_customers(db: Session, count: int = 30) -> dict:
    products = db.query(Product).filter(Product.status == ProductStatus.ACTIVE).all()
    if not products:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            "No active products found — add at least one product before seeding demo customers.",
        )

    created_customers = []
    for _ in range(count):
        customer = Customer(
            name=fake.name(),
            email=fake.unique.email(),
            password="Password123!",
        )
        db.add(customer)
        created_customers.append(customer)
    db.flush()  # get customer.id values before creating transactions/views

    transactions_created = 0
    views_created = 0

    for customer in created_customers:
        # Each customer makes 0-6 purchases spread over the last 60 days,
        # so there's enough history for segmentation, churn, and the
        # forecast/recommendation backtests in the Validation page.
        order_count = random.randint(0, 6)
        for _ in range(order_count):
            product = random.choice(products)
            quantity = random.randint(1, 3)
            tx_date = datetime.utcnow() - timedelta(days=random.randint(0, 60))
            expected_delivery_date = tx_date + timedelta(days=2)

            transaction = Transaction(
                vendor_id=product.vendor_id,
                product_id=product.id,
                customer_id=customer.id,
                quantity=quantity,
                unit_price=product.price,
                total_amount=round(product.price * quantity, 2),
                discount_amount=0.0,
                status=TransactionStatus.COMPLETED,
                transaction_date=tx_date,
                order_status=OrderStatus.DELIVERED,
                expected_delivery_date=expected_delivery_date,
                shipped_at=tx_date + timedelta(days=1),
                delivered_at=expected_delivery_date,
            )
            db.add(transaction)
            transactions_created += 1

        # Browsing activity — customers view more than they buy
        view_count = random.randint(1, 10)
        for _ in range(view_count):
            view = ProductView(
                customer_id=customer.id,
                product_id=random.choice(products).id,
                viewed_at=datetime.utcnow() - timedelta(days=random.randint(0, 60)),
            )
            db.add(view)
            views_created += 1

    db.commit()

    return {
        "customers_created": len(created_customers),
        "transactions_created": transactions_created,
        "product_views_created": views_created,
        "note": "Existing vendors, products, and prior customers/orders were left untouched.",
    }