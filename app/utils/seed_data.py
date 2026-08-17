"""
Seed data generator.

Populates the database with a realistic sample marketplace so the
analytics/report endpoints have something meaningful to compute on:
  - ~12 vendors (mixed statuses)
  - ~8 categories (with a couple of sub-categories)
  - ~60 products spread across vendors/categories
  - inventory rows per product (some deliberately low-stock)
  - ~500 transactions spread over the last 90 days

Run with:
    python -m app.utils.seed_data
"""
import random
import uuid
from datetime import datetime, timedelta

from faker import Faker

from app.database import SessionLocal, init_db
from app.models.vendor import Vendor, VendorStatus, VerificationStatus
from app.models.category import Category
from app.models.product import Product, ProductStatus
from app.models.inventory import Inventory
from app.models.transaction import Transaction, TransactionStatus, OrderStatus
from app.models.customer import Customer
from app.models.promotion import Promotion, DiscountType
from app.models.product_view import ProductView

fake = Faker()
random.seed(42)
Faker.seed(42)

CATEGORY_TREE = {
    "Electronics": ["Mobile Phones", "Laptops & Computers", "Audio"],
    "Fashion": ["Men's Clothing", "Women's Clothing", "Footwear"],
    "Home & Kitchen": ["Furniture", "Kitchen Appliances"],
    "Sports & Outdoors": [],
    "Beauty & Personal Care": [],
    "Books": [],
}


def seed_categories(db):
    categories = []
    for parent_name, children in CATEGORY_TREE.items():
        parent = Category(name=parent_name, description=f"{parent_name} category")
        db.add(parent)
        db.flush()
        categories.append(parent)
        for child_name in children:
            child = Category(name=child_name, description=f"{child_name} category", parent_id=parent.id)
            db.add(child)
            db.flush()
            categories.append(child)
    db.commit()
    return categories


def seed_vendors(db, n=12):
    vendors = []
    statuses = (
        [VendorStatus.ACTIVE] * 8
        + [VendorStatus.PENDING] * 2
        + [VendorStatus.SUSPENDED] * 1
        + [VendorStatus.REJECTED] * 1
    )
    for i in range(n):
        status = statuses[i % len(statuses)]
        vendor = Vendor(
            business_name=fake.unique.company(),
            legal_entity_name=fake.company_suffix() and fake.company(),
            tax_id=fake.unique.bothify(text="TAX-########"),
            primary_category=random.choice(list(CATEGORY_TREE.keys())),
            contact_person=fake.name(),
            email=fake.unique.company_email(),
            password="Password123!",  # demo credential for seeded vendors — see printed summary at end of seeding
            phone=fake.phone_number(),
            address=fake.address().replace("\n", ", "),
            country=fake.country(),
            commission_rate=round(random.uniform(0.05, 0.20), 2),
            status=status,
            verification_status=(
                VerificationStatus.VERIFIED if status == VendorStatus.ACTIVE
                else VerificationStatus.IN_REVIEW if status == VendorStatus.PENDING
                else VerificationStatus.FAILED if status == VendorStatus.REJECTED
                else VerificationStatus.VERIFIED
            ),
            onboarded_at=fake.date_time_between(start_date="-180d", end_date="-30d"),
            approved_at=fake.date_time_between(start_date="-170d", end_date="-20d")
            if status in (VendorStatus.ACTIVE, VendorStatus.SUSPENDED) else None,
        )
        db.add(vendor)
        vendors.append(vendor)
    db.commit()
    return vendors


def seed_products(db, vendors, categories, per_vendor=6):
    products = []
    active_vendors = [v for v in vendors if v.status == VendorStatus.ACTIVE]
    for vendor in active_vendors:
        for _ in range(per_vendor):
            category = random.choice(categories)
            price = round(random.uniform(9.99, 799.99), 2)
            has_rating = random.random() < 0.85  # some products are new / unrated
            product = Product(
                vendor_id=vendor.id,
                category_id=category.id,
                sku=fake.unique.bothify(text="SKU-??????-####").upper(),
                name=fake.catch_phrase(),
                description=fake.sentence(nb_words=12),
                price=price,
                cost_price=round(price * random.uniform(0.5, 0.8), 2),
                status=ProductStatus.ACTIVE,
                rating=round(random.uniform(2.5, 5.0), 1) if has_rating else None,
                rating_count=random.randint(3, 500) if has_rating else 0,
            )
            db.add(product)
            db.flush()

            # Some products are deliberately near/under their reorder level
            low_stock = random.random() < 0.2
            reorder_level = random.randint(5, 20)
            qty = random.randint(0, reorder_level) if low_stock else random.randint(reorder_level + 10, 300)

            inventory = Inventory(
                product_id=product.id,
                warehouse_location=random.choice(["MAIN-WH", "EAST-WH", "WEST-WH"]),
                quantity_available=qty,
                reorder_level=reorder_level,
                reorder_quantity=random.randint(50, 150),
                last_restocked_at=fake.date_time_between(start_date="-60d", end_date="-1d"),
            )
            db.add(inventory)
            products.append(product)
    db.commit()
    return products


def seed_promotions(db, n=4):
    codes = ["WELCOME10", "FESTIVE15", "FLAT50", "SUMMER20"]
    promos = []
    for i in range(min(n, len(codes))):
        promo = Promotion(
            code=codes[i],
            description=fake.sentence(nb_words=6),
            discount_type=DiscountType.PERCENT if i % 2 == 0 else DiscountType.FLAT,
            discount_value=round(random.uniform(10, 25), 2) if i % 2 == 0 else round(random.uniform(20, 60), 2),
            start_date=fake.date_time_between(start_date="-90d", end_date="-60d"),
            end_date=None,
            active=True,
        )
        db.add(promo)
        promos.append(promo)
    db.commit()
    return promos


def seed_transactions(db, products, customers, promotions, n=500):
    if not products:
        return
    customer_ids = [c.id for c in customers] if customers else [None]
    for _ in range(n):
        product = random.choice(products)
        quantity = random.randint(1, 5)
        tx_date = fake.date_time_between(start_date="-90d", end_date="now")
        status = random.choices(
            [TransactionStatus.COMPLETED, TransactionStatus.CANCELLED, TransactionStatus.REFUNDED],
            weights=[0.88, 0.07, 0.05],
        )[0]

        gross = round(product.price * quantity, 2)
        promo = random.choice(promotions) if (promotions and random.random() < 0.2) else None
        discount = 0.0
        if promo:
            if promo.discount_type == DiscountType.PERCENT:
                discount = round(gross * (promo.discount_value / 100.0), 2)
            else:
                discount = round(min(promo.discount_value, gross), 2)

        # Backfill an order lifecycle consistent with the analytics `status`
        # above, so a seeded customer's "My Orders" screen looks realistic
        # (historical orders are well past the 2-day delivery window).
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
            # ~85% of purchases are attributed to a real seeded customer account
            # (so segmentation/recommendation analytics has something to learn from);
            # the rest simulate guest/unauthenticated checkouts.
            customer_id=random.choice(customer_ids) if random.random() < 0.85 else None,
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
    db.commit()


def seed_product_views(db, products, customers, n=800):
    """Browsing signal — customers looked at more products than they bought."""
    if not products or not customers:
        return
    for _ in range(n):
        view = ProductView(
            customer_id=random.choice(customers).id,
            product_id=random.choice(products).id,
            viewed_at=fake.date_time_between(start_date="-90d", end_date="now"),
        )
        db.add(view)
    db.commit()


def seed_customers(db, n=40):
    customers = []
    for _ in range(n):
        has_address = random.random() < 0.8  # a few are left address-less to demo the "address required" flow
        customer = Customer(
            name=fake.name(),
            email=fake.unique.email(),
            password="Password123!",
            address_line=fake.street_address() if has_address else None,
            city=fake.city() if has_address else None,
            state=fake.state() if has_address else None,
            pincode=fake.postcode() if has_address else None,
            phone=fake.phone_number() if has_address else None,
        )
        db.add(customer)
        customers.append(customer)
    db.commit()
    return customers


def run():
    init_db()
    db = SessionLocal()
    try:
        print("Seeding categories...")
        categories = seed_categories(db)
        print(f"  -> {len(categories)} categories created")

        print("Seeding vendors...")
        vendors = seed_vendors(db, n=12)
        print(f"  -> {len(vendors)} vendors created")

        print("Seeding products & inventory...")
        products = seed_products(db, vendors, categories, per_vendor=6)
        print(f"  -> {len(products)} products created")

        print("Seeding customers...")
        customers = seed_customers(db, n=40)
        print(f"  -> {len(customers)} customers created")

        print("Seeding promotions...")
        promotions = seed_promotions(db, n=4)
        print(f"  -> {len(promotions)} promotions created")

        print("Seeding transactions...")
        seed_transactions(db, products, customers, promotions, n=500)
        print("  -> 500 transactions created")

        print("Seeding product views...")
        seed_product_views(db, products, customers, n=800)
        print("  -> 800 product views created")

        print("\nSeed complete.")

        active_vendor = next(v for v in vendors if v.status == VendorStatus.ACTIVE)
        print("\nDemo login credentials (all seeded accounts use the same password):")
        print(f"  Vendor   -> email: {active_vendor.email}  |  password: Password123!")
        print(f"  Customer -> email: {customers[0].email}  |  password: Password123!")
        print(f"  Admin    -> username: admin  |  password: admin123")

    finally:
        db.close()


if __name__ == "__main__":
    run()
