"""Tests for the customer registration/login module."""


def _customer_payload(email="customer1@example.com"):
    return {
        "name": "Alex Doe",
        "email": email,
        "password": "CustPass123",
    }


def test_register_customer(client):
    response = client.post("/customer/register", json=_customer_payload())
    assert response.status_code == 201
    data = response.json()
    assert data["name"] == "Alex Doe"
    assert "password" not in data


def test_register_duplicate_email_rejected(client):
    client.post("/customer/register", json=_customer_payload())
    response = client.post("/customer/register", json=_customer_payload())
    assert response.status_code == 400


def test_login_success(client):
    client.post("/customer/register", json=_customer_payload())
    response = client.post("/customer/login", json={
        "email": "customer1@example.com",
        "password": "CustPass123",
    })
    assert response.status_code == 200
    data = response.json()
    assert data["name"] == "Alex Doe"
    assert "customer_id" in data


def test_login_wrong_password_rejected(client):
    client.post("/customer/register", json=_customer_payload())
    response = client.post("/customer/login", json={
        "email": "customer1@example.com",
        "password": "WrongPassword",
    })
    assert response.status_code == 401


def test_login_unknown_email_rejected(client):
    response = client.post("/customer/login", json={
        "email": "doesnotexist@example.com",
        "password": "whatever",
    })
    assert response.status_code == 401


def test_customer_can_browse_active_products(client):
    """
    The customer dashboard lists active products across all vendors via
    the existing GET /products?status=active endpoint - confirms no
    vendor_id filter is required for that to work.
    """
    response = client.get("/products?status=active")
    assert response.status_code == 200
    assert isinstance(response.json(), list)
