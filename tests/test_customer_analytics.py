"""Tests for Customer Behaviour & Recommendation Analytics (Milestone 2, Module 4)."""


def _make_active_vendor(client, email="ca-vendor@example.com"):
    reg = client.post("/vendors/register", json={
        "business_name": "Behaviour Co",
        "contact_person": "Sam Lee",
        "email": email,
        "password": "TestPass123",
        "phone": "+1-555-0400",
        "commission_rate": 0.10,
    })
    vendor_id = reg.json()["id"]
    client.patch(f"/vendors/{vendor_id}/approve", json={})
    return vendor_id


def _make_product(client, vendor_id, sku, name="Product", price=30.0, qty=100):
    response = client.post("/products", json={
        "vendor_id": vendor_id, "sku": sku, "name": name, "price": price, "initial_quantity": qty,
    })
    return response.json()["id"]


def _make_customer(client, email):
    reg = client.post("/customer/register", json={
        "name": "Test Customer", "email": email, "password": "CustPass123",
    })
    customer_id = reg.json()["id"]
    client.put(f"/customer/{customer_id}/address", json={
        "address_line": "10 Analytics Ave", "city": "Datatown",
        "state": "State", "pincode": "400001", "phone": "+1-555-0300",
    })
    return customer_id


def test_segments_empty_when_no_customers(client):
    response = client.get("/customer-analytics/segments")
    assert response.status_code == 200
    assert response.json()["clusters"] == []


def test_segments_reflect_purchase_activity(client):
    vendor_id = _make_active_vendor(client)
    product_id = _make_product(client, vendor_id, sku="SKU-CA-1")
    customer_id = _make_customer(client, "segment-buyer@example.com")

    client.post("/customer/checkout", json={
        "customer_id": customer_id,
        "items": [{"product_id": product_id, "quantity": 2}],
    })

    response = client.get("/customer-analytics/segments")
    assert response.status_code == 200
    data = response.json()
    assert len(data["customers"]) == 1
    assert data["customers"][0]["frequency"] == 1


def test_customer_profile_includes_purchase_history(client):
    vendor_id = _make_active_vendor(client)
    product_id = _make_product(client, vendor_id, sku="SKU-CA-2", name="Yoga Mat")
    customer_id = _make_customer(client, "profile-buyer@example.com")

    client.post("/customer/checkout", json={
        "customer_id": customer_id,
        "items": [{"product_id": product_id, "quantity": 1}],
    })

    response = client.get(f"/customer-analytics/customer/{customer_id}/profile")
    assert response.status_code == 200
    profile = response.json()
    assert profile["total_orders"] == 1
    assert len(profile["recent_purchases"]) == 1


def test_customer_revenue_analysis_reflects_purchases(client):
    vendor_id = _make_active_vendor(client, "ca-vendor-revenue@example.com")
    product_id = _make_product(client, vendor_id, sku="SKU-CA-REV", name="Desk Lamp", price=45.0)
    customer_id = _make_customer(client, "revenue-buyer@example.com")

    client.post("/customer/checkout", json={
        "customer_id": customer_id,
        "items": [{"product_id": product_id, "quantity": 2}],
    })

    response = client.get(f"/customer-analytics/customer/{customer_id}/revenue-analysis")
    assert response.status_code == 200
    data = response.json()
    assert data["total_orders"] == 1
    assert data["total_spent"] == 90.0
    assert isinstance(data["category_breakdown"], list)
    assert len(data["monthly_trend"]) == 1


def test_customer_revenue_analysis_empty_for_no_purchases(client):
    customer_id = _make_customer(client, "no-purchases@example.com")
    response = client.get(f"/customer-analytics/customer/{customer_id}/revenue-analysis")
    assert response.status_code == 200
    data = response.json()
    assert data["total_spent"] == 0.0
    assert data["total_orders"] == 0
    assert data["monthly_trend"] == []


def test_recommendations_fallback_to_popularity_for_cold_start(client):
    vendor_id = _make_active_vendor(client)
    p1 = _make_product(client, vendor_id, sku="SKU-CA-3", name="Popular Item")
    other_buyer = _make_customer(client, "other-buyer@example.com")
    client.post("/customer/checkout", json={
        "customer_id": other_buyer,
        "items": [{"product_id": p1, "quantity": 1}],
    })

    new_customer = _make_customer(client, "new-customer@example.com")
    response = client.get(f"/customer-analytics/recommendations/{new_customer}")
    assert response.status_code == 200
    data = response.json()
    assert data["strategy"] == "popularity (cold start)"
    assert len(data["recommendations"]) >= 1


def test_churn_risk_flags_customers_with_no_purchases(client):
    _make_customer(client, "never-bought@example.com")
    response = client.get("/customer-analytics/churn-risk")
    assert response.status_code == 200
    risks = response.json()
    assert any(r["risk_level"] == "New / No Purchases" for r in risks)


def test_customer_analytics_dashboard_returns_summary(client):
    response = client.get("/customer-analytics/dashboard")
    assert response.status_code == 200
    data = response.json()
    for key in ("total_customers", "segments", "churn_risk", "high_risk_count"):
        assert key in data
