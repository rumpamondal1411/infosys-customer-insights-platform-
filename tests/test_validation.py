"""Tests for persisted inventory forecasting (Step 1) and the validation
module that checks it, segmentation, and recommendations against
historical data (Step 4)."""
from datetime import datetime, timedelta


def _make_active_vendor(client, email="val-vendor@example.com"):
    reg = client.post("/vendors/register", json={
        "business_name": "Validation Co",
        "contact_person": "Kim Park",
        "email": email,
        "password": "TestPass123",
        "phone": "+1-555-0500",
        "commission_rate": 0.10,
    })
    vendor_id = reg.json()["id"]
    client.patch(f"/vendors/{vendor_id}/approve", json={})
    return vendor_id


def _make_product(client, vendor_id, sku, price=20.0, qty=500):
    response = client.post("/products", json={
        "vendor_id": vendor_id, "sku": sku, "name": "Forecast Widget",
        "price": price, "initial_quantity": qty,
    })
    return response.json()["id"]


def _sell_over_time(client, vendor_id, product_id, days_back_list, quantity=2):
    """Creates completed transactions dated across a spread of past days,
    so there's enough history for the backtest to have a train/test split."""
    for days_back in days_back_list:
        tx_date = (datetime.utcnow() - timedelta(days=days_back)).isoformat()
        client.post("/transactions", json={
            "vendor_id": vendor_id, "product_id": product_id, "quantity": quantity,
            "transaction_date": tx_date,
        })


# --------------------------------------------------------- Step 1: persisted forecasting

def test_forecast_is_persisted_with_confidence_level(client):
    vendor_id = _make_active_vendor(client)
    product_id = _make_product(client, vendor_id, sku="SKU-FC-1")
    _sell_over_time(client, vendor_id, product_id, days_back_list=[25, 20, 15, 10, 5, 2])

    response = client.get(f"/inventory/forecast/{product_id}")
    assert response.status_code == 201
    forecast = response.json()
    assert forecast["product_id"] == product_id
    assert forecast["predicted_stock"] >= 0
    assert 0 <= forecast["confidence_level"] <= 1
    assert forecast["horizon_days"] == 7

    history = client.get(f"/inventory/forecast/{product_id}/history")
    assert history.status_code == 200
    assert len(history.json()) == 1


def test_forecast_history_accumulates_multiple_runs(client):
    vendor_id = _make_active_vendor(client)
    product_id = _make_product(client, vendor_id, sku="SKU-FC-2")
    _sell_over_time(client, vendor_id, product_id, days_back_list=[20, 10, 3])

    client.get(f"/inventory/forecast/{product_id}")
    client.get(f"/inventory/forecast/{product_id}")

    history = client.get(f"/inventory/forecast/{product_id}/history")
    assert len(history.json()) == 2


# --------------------------------------------------------- Step 4: validation

def test_forecast_accuracy_backtests_against_held_out_sales(client):
    vendor_id = _make_active_vendor(client)
    product_id = _make_product(client, vendor_id, sku="SKU-VAL-1")
    # 30 days of steady daily-ish sales so train/test windows both have data
    _sell_over_time(client, vendor_id, product_id,
                     days_back_list=[28, 24, 21, 18, 15, 12, 9, 6, 4, 2], quantity=3)

    response = client.get("/validation/forecast-accuracy")
    assert response.status_code == 200
    data = response.json()
    assert data["products_evaluated"] >= 1
    assert 0 <= data["overall_accuracy_pct"] <= 100
    assert data["threshold_pct"] == 80.0
    assert "meets_threshold" in data


def test_forecast_accuracy_handles_no_data(client):
    response = client.get("/validation/forecast-accuracy")
    assert response.status_code == 200
    data = response.json()
    assert data["products_evaluated"] == 0
    assert data["meets_threshold"] is False


def test_segmentation_quality_reports_silhouette(client):
    response = client.get("/validation/segmentation-quality")
    assert response.status_code == 200
    data = response.json()
    assert data["threshold_pct"] == 85.0
    assert "quality_pct" in data


def test_recommendation_relevance_handles_no_repeat_customers(client):
    response = client.get("/validation/recommendation-relevance")
    assert response.status_code == 200
    data = response.json()
    assert data["customers_evaluated"] == 0
    assert data["meets_threshold"] is False


def test_recommendation_relevance_evaluates_repeat_customers(client):
    vendor_id = _make_active_vendor(client)
    p1 = _make_product(client, vendor_id, sku="SKU-VAL-2")
    p2 = _make_product(client, vendor_id, sku="SKU-VAL-3")

    reg = client.post("/customer/register", json={
        "name": "Repeat Buyer", "email": "repeat-buyer@example.com", "password": "CustPass123",
    })
    customer_id = reg.json()["id"]
    client.put(f"/customer/{customer_id}/address", json={
        "address_line": "5 Validation St", "city": "Testville",
        "state": "State", "pincode": "700001", "phone": "+1-555-0400",
    })

    client.post("/customer/checkout", json={"customer_id": customer_id, "items": [{"product_id": p1, "quantity": 1}]})
    client.post("/customer/checkout", json={"customer_id": customer_id, "items": [{"product_id": p2, "quantity": 1}]})

    response = client.get("/validation/recommendation-relevance")
    assert response.status_code == 200
    data = response.json()
    assert data["customers_evaluated"] >= 1
    assert data["threshold_pct"] == 75.0


def test_validation_report_returns_all_three_sections(client):
    response = client.get("/validation/report")
    assert response.status_code == 200
    data = response.json()
    for key in ("forecast_accuracy", "segmentation_quality", "recommendation_relevance"):
        assert key in data
