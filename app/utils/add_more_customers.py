"""
Additive customer + order seeder.

Unlike `seed_data.py` (which builds the whole database from scratch),
this script ONLY ADDS new rows:
  - ~100 new customers
  - a handful of orders (transactions) for each of them, using whatever
    products/vendors/promotions already exist in the database

It never deletes, truncates, or modifies anything that's already there —
so any customers or products you've added by hand are left exactly as
they are. Safe to re-run: it keeps adding on top of what exists.

Run with:
    python -m app.utils.add_more_customers

Optional: change how many customers to add by passing a number:
    python -m app.utils.add_more_customers 100
"""
import json
import random
import sys
import uuid
from datetime import datetime, timedelta
from pathlib import Path

from faker import Faker

from app.database import SessionLocal, init_db
from app.models.product import Product, ProductStatus
from app.models.promotion import Promotion
from app.models.customer import Customer
from app.models.transaction import Transaction, TransactionStatus, OrderStatus

fake = Faker()

# Tracks which customer IDs were added by this script (see remove_added_customers.py).
# Kept next to this file rather than in the DB so it survives independent of schema changes.
_BATCH_LOG_PATH = Path(__file__).parent / "_added_customer_batches.json"

# Not seeding with a fixed random.seed()/Faker.seed() on purpose here —
# we want genuinely new/unique people and emails each time this is run,
# not the same 100 names seed_data.py would already have produced.


def add_customers(db, n=100):
    """Create n new customers with guaranteed-unique emails
    (checks against emails already in the database)."""
    existing_emails = {e for (e,) in db.query(Customer.email).all()}
    new_customers = []

    attempts = 0
    while len(new_customers) < n and attempts < n * 20:
        attempts += 1
        email = fake.unique.email()
        if email in existing_emails:
            continue
        existing_emails.add(email)

        customer = Customer(
            name=fake.name(),
            email=email,
            password="Password123!",
            address_line=fake.street_address(),
            city=fake.city(),
            state=fake.state(),
            pincode=fake.postcode(),
            phone=fake.phone_number(),
            created_at=fake.date_time_between(start_date="-60d", end_date="now"),
        )
        db.add(customer)
        new_customers.append(customer)

    db.commit()
    return new_customers


def add_orders_for_customers(db, customers, min_orders=1, max_orders=4):
    """Give each new customer a few orders against existing active products,
    so they show up with real order history / analytics."""
    products = (
        db.query(Product)
        .filter(Product.status == ProductStatus.ACTIVE)
        .all()
    )
    if not products:
        print("  ! No active products found — skipping order creation.")
        return 0

    promotions = db.query(Promotion).filter(Promotion.active == True).all()  # noqa: E712

    orders_created = 0
    for customer in customers:
        num_orders = random.randint(min_orders, max_orders)
        for _ in range(num_orders):
            product = random.choice(products)
            quantity = random.randint(1, 5)
            gross = round(product.price * quantity, 2)

            promo = random.choice(promotions) if (promotions and random.random() < 0.2) else None
            discount = 0.0
            if promo:
                if promo.discount_type.value == "percent":
                    discount = round(gross * (promo.discount_value / 100.0), 2)
                else:
                    discount = round(min(promo.discount_value, gross), 2)

            status = random.choices(
                [TransactionStatus.COMPLETED, TransactionStatus.CANCELLED, TransactionStatus.REFUNDED],
                weights=[0.88, 0.07, 0.05],
            )[0]

            tx_date = fake.date_time_between(start_date=customer.created_at, end_date="now")

            # Backfill an order lifecycle consistent with `status` above, so
            # these customers' "My Orders" screen shows real placed/shipped/
            # delivered/cancelled/returned history instead of every order
            # being stuck on "Placed" (these are historical orders, well
            # past the 2-day delivery window).
            expected_delivery_date = tx_date + timedelta(days=2)
            shipped_at = tx_date + timedelta(days=1)
            if status == TransactionStatus.CANCELLED:
                order_status = OrderStatus.CANCELLED
                cancelled_at = tx_date + timedelta(hours=random.randint(1, 20))
                delivered_at = None
                returned_at = None
            elif status == TransactionStatus.REFUNDED:
                order_status = OrderStatus.RETURNED
                delivered_at = expected_delivery_date
                returned_at = expected_delivery_date + timedelta(days=random.randint(1, 5))
                cancelled_at = None
            else:
                order_status = OrderStatus.DELIVERED
                delivered_at = expected_delivery_date
                cancelled_at = None
                returned_at = None

            transaction = Transaction(
                vendor_id=product.vendor_id,
                product_id=product.id,
                customer_id=customer.id,
                quantity=quantity,
                unit_price=product.price,
                total_amount=round(gross - discount, 2),
                discount_amount=discount,
                promotion_id=promo.id if promo else None,
                status=status,
                transaction_date=tx_date,
                order_ref=f"ORD-{uuid.uuid4().hex[:10].upper()}",
                order_status=order_status,
                expected_delivery_date=expected_delivery_date,
                shipped_at=shipped_at,
                delivered_at=delivered_at,
                cancelled_at=cancelled_at,
                returned_at=returned_at,
            )
            db.add(transaction)
            orders_created += 1

    db.commit()
    return orders_created


def _log_batch(customer_ids):
    """Appends this run's new customer IDs to the tracking file, so
    remove_added_customers.py can later delete exactly these rows and
    nothing else."""
    batches = []
    if _BATCH_LOG_PATH.exists():
        try:
            batches = json.loads(_BATCH_LOG_PATH.read_text())
        except (json.JSONDecodeError, OSError):
            batches = []

    batches.append({
        "added_at": datetime.utcnow().isoformat(),
        "customer_ids": customer_ids,
    })
    _BATCH_LOG_PATH.write_text(json.dumps(batches, indent=2))


def run(n=100):
    init_db()
    db = SessionLocal()
    try:
        print(f"Adding {n} new customers (existing customers are left untouched)...")
        customers = add_customers(db, n=n)
        print(f"  -> {len(customers)} new customers added")

        print("Adding orders for the new customers (existing products/orders untouched)...")
        order_count = add_orders_for_customers(db, customers)
        print(f"  -> {order_count} new orders added")

        _log_batch([c.id for c in customers])

        print("\nDone. Nothing existing was deleted or modified.")
        print(f"(This batch's customer IDs were recorded in {_BATCH_LOG_PATH.name} "
              f"so they can be cleanly removed later with remove_added_customers.py)")
        if customers:
            print(f"\nSample login for one of the new customers:")
            print(f"  email: {customers[0].email}  |  password: Password123!")

    finally:
        db.close()


if __name__ == "__main__":
    count = int(sys.argv[1]) if len(sys.argv) > 1 else 100
    run(n=count)