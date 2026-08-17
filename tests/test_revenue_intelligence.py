"""Tests for Sales Analytics & Revenue Intelligence (Milestone 2, Module 3)."""


def _make_active_vendor(client, email="ri-vendor@example.com"):
    reg = client.post("/vendors/register", json={
        "business_name": "Revenue Corp",
        "contact_person": "Jane Roe",
        "email": email,
        "password": "TestPass123",
        "phone": "+1-555-0300",
        "commission_rate": 0.10,
    })
    vendor_id = reg.json()["id"]
    client.patch(f"/vendors/{vendor_id}/approve", json={})
    return vendor_id


def _make_product(client, vendor_id, sku="SKU-RI-1", price=40.0, cost_price=20.0, qty=50):
    response = client.post("/products", json={
        "vendor_id": vendor_id, "sku": sku, "name": "Analytics Widget",
        "price": price, "cost_price": cost_price, "initial_quantity": qty,
    })
    return response.json()["id"]


def _sell(client, vendor_id, product_id, quantity=1):
    return client.post("/transactions", json={
        "vendor_id": vendor_id, "product_id": product_id, "quantity": quantity,
    })


def test_gmv_and_growth_reflects_sales(client):
    vendor_id = _make_active_vendor(client)
    product_id = _make_product(client, vendor_id)
    _sell(client, vendor_id, product_id, quantity=3)

    response = client.get("/revenue-intelligence/gmv-growth")
    assert response.status_code == 200
    data = response.json()
    assert data["revenue"] == 120.0
    assert data["gmv"] >= data["revenue"]


def test_profit_margins_computed_from_cost_price(client):
    vendor_id = _make_active_vendor(client)
    product_id = _make_product(client, vendor_id, price=40.0, cost_price=20.0)
    _sell(client, vendor_id, product_id, quantity=2)

    response = client.get("/revenue-intelligence/profit-margins")
    assert response.status_code == 200
    margins = response.json()
    assert len(margins) == 1
    assert margins[0]["margin_pct"] == 50.0


def test_promotion_performance_tracks_discount_usage(client):
    vendor_id = _make_active_vendor(client)
    product_id = _make_product(client, vendor_id, price=100.0)

    client.post("/promotions", json={"code": "RI10", "discount_type": "percent", "discount_value": 10})
    client.post("/transactions", json={
        "vendor_id": vendor_id, "product_id": product_id, "quantity": 1,
        "discount_amount": 10.0,
    })

    response = client.get("/revenue-intelligence/promotion-performance")
    assert response.status_code == 200


def test_revenue_intelligence_dashboard_returns_all_sections(client):
    vendor_id = _make_active_vendor(client)
    product_id = _make_product(client, vendor_id)
    _sell(client, vendor_id, product_id, quantity=1)

    response = client.get("/revenue-intelligence/dashboard")
    assert response.status_code == 200
    data = response.json()
    for key in ("gmv_and_growth", "refunds", "sales_by_region", "sales_by_time",
                "top_margin_products", "promotion_performance"):
        assert key in data
