"""
One-time migration: adds the new columns needed for wishlist/address/
payment-method features to tables that ALREADY EXIST in your database.

Why this is needed: SQLAlchemy's `Base.metadata.create_all()` (called on
every app startup) only creates tables that don't exist yet — it does NOT
add new columns to a table that's already there. Since your `customers`
and `transactions` tables already exist with real data, the new
`address_line`/`city`/`state`/`pincode`/`phone` columns on Customer and
the new `payment_method` column on Transaction need to be added manually,
once, via this script. (The new `wishlist` table needs no migration —
it's brand new, so `create_all()` handles it automatically on next
startup.)

This is 100% additive and safe: existing rows just get NULL / the default
value in the new columns. Nothing is deleted or overwritten.

Usage (run once, from the project root):
    python -m app.utils.migrate_add_columns
"""
import sqlite3

from app.database import engine


def _get_db_path() -> str:
    # database.py builds the engine from settings.database_url (e.g.
    # "sqlite:///data/shopsense.db") — there's no separate DB_PATH constant,
    # so pull the file path directly off the engine's URL.
    url = str(engine.url)
    return url.replace("sqlite:///", "")


def _add_column_if_missing(cursor, table: str, column: str, definition: str):
    cursor.execute(f"PRAGMA table_info({table})")
    existing_columns = {row[1] for row in cursor.fetchall()}
    if column in existing_columns:
        print(f"  - {table}.{column} already exists, skipping")
        return
    cursor.execute(f"ALTER TABLE {table} ADD COLUMN {column} {definition}")
    print(f"  + added {table}.{column}")


def run():
    db_path = _get_db_path()
    print(f"Migrating database at: {db_path}")
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    print("customers table:")
    _add_column_if_missing(cursor, "customers", "address_line", "VARCHAR(255)")
    _add_column_if_missing(cursor, "customers", "city", "VARCHAR(100)")
    _add_column_if_missing(cursor, "customers", "state", "VARCHAR(100)")
    _add_column_if_missing(cursor, "customers", "pincode", "VARCHAR(20)")
    _add_column_if_missing(cursor, "customers", "phone", "VARCHAR(20)")

    print("transactions table:")
    _add_column_if_missing(
        cursor, "transactions", "payment_method", "VARCHAR(20) DEFAULT 'cod' NOT NULL"
    )
    _add_column_if_missing(cursor, "transactions", "order_ref", "VARCHAR(50)")
    _add_column_if_missing(
        cursor, "transactions", "order_status", "VARCHAR(20) DEFAULT 'placed' NOT NULL"
    )
    _add_column_if_missing(cursor, "transactions", "expected_delivery_date", "DATETIME")
    _add_column_if_missing(cursor, "transactions", "shipped_at", "DATETIME")
    _add_column_if_missing(cursor, "transactions", "delivered_at", "DATETIME")
    _add_column_if_missing(cursor, "transactions", "cancelled_at", "DATETIME")
    _add_column_if_missing(cursor, "transactions", "cancellation_reason", "VARCHAR(255)")
    _add_column_if_missing(cursor, "transactions", "returned_at", "DATETIME")
    _add_column_if_missing(cursor, "transactions", "return_reason", "VARCHAR(255)")

    print("products table:")
    _add_column_if_missing(cursor, "products", "rating", "FLOAT")
    _add_column_if_missing(cursor, "products", "rating_count", "INTEGER DEFAULT 0 NOT NULL")

    conn.commit()
    conn.close()
    print("\nMigration complete. Your existing data was not modified.")


if __name__ == "__main__":
    run()