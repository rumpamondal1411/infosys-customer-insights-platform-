"""
Shared pytest fixtures. Uses an isolated in-memory SQLite database per test
session so tests never touch the real data/shopsense.db file.
"""
import shutil
from pathlib import Path

import pytest
from sqlalchemy import create_engine
from sqlalchemy.pool import StaticPool
from sqlalchemy.orm import sessionmaker
from fastapi.testclient import TestClient

from app.database import Base, get_db
from app.main import app

from app.models import vendor, category, product, inventory, transaction, customer, analytics_snapshot

TEST_DATABASE_URL = "sqlite:///:memory:"

engine = create_engine(
    TEST_DATABASE_URL,
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


@pytest.fixture(scope="function")
def db_session():
    Base.metadata.create_all(bind=engine)
    session = TestingSessionLocal()
    try:
        yield session
    finally:
        session.close()
        Base.metadata.drop_all(bind=engine)


@pytest.fixture(scope="function")
def client(db_session):
    def override_get_db():
        try:
            yield db_session
        finally:
            pass

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()


@pytest.fixture(autouse=True)
def clean_uploaded_test_images():
    """
    Product image tests write real files to app/static/uploads/products/.
    Since product IDs restart from 1 in each test's fresh in-memory DB,
    leftover files from a previous run could otherwise be mistaken for
    output of the current test — so this clears the folder before and
    after every test.
    """
    upload_dir = Path("app/static/uploads/products")
    upload_dir.mkdir(parents=True, exist_ok=True)

    def _clear():
        for f in upload_dir.glob("*"):
            if f.name != ".gitkeep":
                f.unlink()

    _clear()
    yield
    _clear()
