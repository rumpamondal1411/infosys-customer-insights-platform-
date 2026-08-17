"""
Database engine and session management.

Uses SQLAlchemy 2.0 style. SQLite is used by default for Week 1 so the
project runs with zero external infrastructure; DATABASE_URL can be swapped
for PostgreSQL/MySQL in later weeks without changing any model or service
code (that's the point of the ORM abstraction).
"""
import os
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, DeclarativeBase

from app.config import settings

# Ensure the folder for the sqlite file exists
if settings.database_url.startswith("sqlite"):
    os.makedirs("data", exist_ok=True)

connect_args = {"check_same_thread": False} if settings.database_url.startswith("sqlite") else {}

engine = create_engine(settings.database_url, connect_args=connect_args)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


class Base(DeclarativeBase):
    pass


def get_db():
    """FastAPI dependency that yields a DB session and closes it afterwards."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db():
    """Create all tables. Called on app startup and by the seeding script."""
    # Import models here so they are registered on Base.metadata before create_all
    from app.models import (  # noqa: F401
        vendor, category, product, inventory, transaction, customer,
        promotion, product_view, inventory_forecast, wishlist,
        analytics_snapshot,
    )
    Base.metadata.create_all(bind=engine)