"""Tests for the customer search & buy flow (Milestone 2 dashboard upgrade)."""


def _make_active_vendor(client, email="vendor@example.com"):
    reg = client.post("/vendors/register", json={
        "business_name": "Acme Supplies",
        "contact_person": "John Smith",
        "email": email,
        "password": "TestPass123",
        "phone": "+1-555-0200",
        "commission_rate": 0.10,
    })
    vendor_id = reg.json()["id"]
    client.patch(f"/vendors/{vendor_id}/approve", json={})
    return vendor_id


def _make_product(client, vendor_id, sku="SKU-BUY-1", name="Wireless Mouse", price=25.0, qty=20):
    response = client.post("/products", json={
        "vendor_id": vendor_id, "sku": sku, "name": name,
        "price": price, "initial_quantity": qty,
    })
    return response.json()["id"]


def _make_customer(client, email="buyer@example.com", with_address=True):
    reg = client.post("/customer/register", json={
        "name": "Priya Sharma", "email": email, "password": "CustPass123",
    })
    customer_id = reg.json()["id"]
    if with_address:
        client.put(f"/customer/{customer_id}/address", json={
            "address_line": "221B Baker Street",
            "city": "Metropolis",
            "state": "State",
            "pincode": "100001",
            "phone": "+1-555-0100",
        })
    return customer_id


def test_product_search_filters_by_name(client):
    vendor_id = _make_active_vendor(client)
    _make_product(client, vendor_id, sku="SKU-SEARCH-1", name="Bluetooth Headphones")
    _make_product(client, vendor_id, sku="SKU-SEARCH-2", name="Kitchen Blender")

    response = client.get("/products?status=active&search=headphones")
    assert response.status_code == 200
    results = response.json()
    assert len(results) == 1
    assert "Headphones" in results[0]["name"]


def test_buy_now_creates_transaction_and_deducts_stock(client):
    vendor_id = _make_active_vendor(client)
    product_id = _make_product(client, vendor_id, qty=10)
    customer_id = _make_customer(client)

    response = client.post("/customer/checkout", json={
        "customer_id": customer_id,
        "items": [{"product_id": product_id, "quantity": 2}],
    })
    assert response.status_code == 201
    order = response.json()
    assert order["grand_total"] == 50.0
    assert len(order["items"]) == 1

    inv = client.get(f"/inventory/{product_id}")
    assert inv.json()["quantity_available"] == 8

    orders = client.get(f"/customer/{customer_id}/orders")
    assert orders.status_code == 200
    assert len(orders.json()) == 1


def test_checkout_rejects_insufficient_stock(client):
    vendor_id = _make_active_vendor(client)
    product_id = _make_product(client, vendor_id, qty=1)
    customer_id = _make_customer(client)

    response = client.post("/customer/checkout", json={
        "customer_id": customer_id,
        "items": [{"product_id": product_id, "quantity": 5}],
    })
    assert response.status_code == 400


def test_checkout_applies_promotion_code(client):
    vendor_id = _make_active_vendor(client)
    product_id = _make_product(client, vendor_id, price=100.0, qty=10)
    customer_id = _make_customer(client)

    promo = client.post("/promotions", json={
        "code": "SAVE10", "discount_type": "percent", "discount_value": 10,
    })
    assert promo.status_code == 201

    response = client.post("/customer/checkout", json={
        "customer_id": customer_id,
        "items": [{"product_id": product_id, "quantity": 1}],
        "promotion_code": "SAVE10",
    })
    assert response.status_code == 201
    order = response.json()
    assert order["total_discount"] == 10.0
    assert order["grand_total"] == 90.0


def test_track_view_records_engagement(client):
    vendor_id = _make_active_vendor(client)
    product_id = _make_product(client, vendor_id)
    customer_id = _make_customer(client)

    response = client.post(f"/customer/{customer_id}/track-view/{product_id}")
    assert response.status_code == 201
    assert response.json()["tracked"] is True


def test_checkout_requires_delivery_address(client):
    vendor_id = _make_active_vendor(client)
    product_id = _make_product(client, vendor_id, qty=10)
    customer_id = _make_customer(client, email="no-address-buyer@example.com", with_address=False)

    response = client.post("/customer/checkout", json={
        "customer_id": customer_id,
        "items": [{"product_id": product_id, "quantity": 1}],
    })
    assert response.status_code == 400
    assert "ADDRESS_REQUIRED" in response.json()["detail"]


def test_checkout_succeeds_once_address_is_saved(client):
    vendor_id = _make_active_vendor(client)
    product_id = _make_product(client, vendor_id, qty=10)
    customer_id = _make_customer(client, email="fills-address-later@example.com", with_address=False)

    rejected = client.post("/customer/checkout", json={
        "customer_id": customer_id,
        "items": [{"product_id": product_id, "quantity": 1}],
    })
    assert rejected.status_code == 400

    client.put(f"/customer/{customer_id}/address", json={
        "address_line": "42 Galaxy Way", "city": "Springfield",
        "pincode": "500001", "phone": "+1-555-0999",
    })

    accepted = client.post("/customer/checkout", json={
        "customer_id": customer_id,
        "items": [{"product_id": product_id, "quantity": 1}],
    })
    assert accepted.status_code == 201


def test_checkout_response_includes_expected_delivery_date(client):
    vendor_id = _make_active_vendor(client)
    product_id = _make_product(client, vendor_id, qty=10)
    customer_id = _make_customer(client)

    response = client.post("/customer/checkout", json={
        "customer_id": customer_id,
        "items": [{"product_id": product_id, "quantity": 1}],
    })
    assert response.status_code == 201
    order = response.json()
    assert "expected_delivery_date" in order

    orders = client.get(f"/customer/{customer_id}/orders").json()
    assert orders[0]["order_status"] == "placed"
    assert orders[0]["expected_delivery_date"] is not None


def test_cancel_order_before_delivery_restocks_inventory(client):
    vendor_id = _make_active_vendor(client)
    product_id = _make_product(client, vendor_id, qty=10)
    customer_id = _make_customer(client)

    checkout = client.post("/customer/checkout", json={
        "customer_id": customer_id,
        "items": [{"product_id": product_id, "quantity": 3}],
    })
    transaction_id = checkout.json()["items"][0]["transaction_id"]

    inv_after_buy = client.get(f"/inventory/{product_id}").json()["quantity_available"]
    assert inv_after_buy == 7

    cancel = client.post(f"/customer/{customer_id}/orders/{transaction_id}/cancel", json={"reason": "Changed my mind"})
    assert cancel.status_code == 200
    assert cancel.json()["order_status"] == "cancelled"
    assert cancel.json()["status"] == "cancelled"

    inv_after_cancel = client.get(f"/inventory/{product_id}").json()["quantity_available"]
    assert inv_after_cancel == 10


def test_cannot_cancel_an_already_cancelled_order(client):
    vendor_id = _make_active_vendor(client)
    product_id = _make_product(client, vendor_id, qty=5)
    customer_id = _make_customer(client)

    checkout = client.post("/customer/checkout", json={
        "customer_id": customer_id, "items": [{"product_id": product_id, "quantity": 1}],
    })
    transaction_id = checkout.json()["items"][0]["transaction_id"]

    client.post(f"/customer/{customer_id}/orders/{transaction_id}/cancel", json={})
    second_attempt = client.post(f"/customer/{customer_id}/orders/{transaction_id}/cancel", json={})
    assert second_attempt.status_code == 400


def test_cannot_return_an_order_that_has_not_been_delivered(client):
    vendor_id = _make_active_vendor(client)
    product_id = _make_product(client, vendor_id, qty=5)
    customer_id = _make_customer(client)

    checkout = client.post("/customer/checkout", json={
        "customer_id": customer_id, "items": [{"product_id": product_id, "quantity": 1}],
    })
    transaction_id = checkout.json()["items"][0]["transaction_id"]

    response = client.post(f"/customer/{customer_id}/orders/{transaction_id}/return", json={})
    assert response.status_code == 400


def test_return_after_delivery_refunds_and_restocks(client, db_session):
    vendor_id = _make_active_vendor(client)
    product_id = _make_product(client, vendor_id, qty=5)
    customer_id = _make_customer(client)

    checkout = client.post("/customer/checkout", json={
        "customer_id": customer_id, "items": [{"product_id": product_id, "quantity": 2}],
    })
    transaction_id = checkout.json()["items"][0]["transaction_id"]

    # Without the 2-day delivery window having elapsed, a return should be rejected.
    too_early = client.post(f"/customer/{customer_id}/orders/{transaction_id}/return", json={})
    assert too_early.status_code == 400

    # Simulate the 2-day delivery window having elapsed. A real deployment
    # gets here purely by waiting — the app's own elapsed-time sync logic
    # (order_service._sync_order_status) will flip placed -> shipped ->
    # delivered on its own once enough real time has passed; this just
    # fast-forwards the clock for the test.
    from datetime import datetime, timedelta
    from app.models.transaction import Transaction

    transaction = db_session.query(Transaction).filter(Transaction.id == transaction_id).first()
    transaction.transaction_date = datetime.utcnow() - timedelta(days=3)
    transaction.expected_delivery_date = datetime.utcnow() - timedelta(days=1)
    db_session.commit()

    orders = client.get(f"/customer/{customer_id}/orders").json()
    assert orders[0]["order_status"] == "delivered"

    inv_before_return = client.get(f"/inventory/{product_id}").json()["quantity_available"]
    assert inv_before_return == 3

    return_response = client.post(f"/customer/{customer_id}/orders/{transaction_id}/return", json={"reason": "Wrong size"})
    assert return_response.status_code == 200
    assert return_response.json()["order_status"] == "returned"
    assert return_response.json()["status"] == "refunded"

    inv_after_return = client.get(f"/inventory/{product_id}").json()["quantity_available"]
    assert inv_after_return == 5


def test_product_response_includes_rating_and_stock_fields(client):
    vendor_id = _make_active_vendor(client)
    product_id = _make_product(client, vendor_id, qty=4)

    response = client.get(f"/products/{product_id}")
    assert response.status_code == 200
    data = response.json()
    assert data["quantity_available"] == 4
    assert "rating" in data
    assert "rating_count" in data


def test_product_shows_zero_stock_when_out_of_stock(client):
    vendor_id = _make_active_vendor(client)
    product_id = _make_product(client, vendor_id, qty=1)
    customer_id = _make_customer(client)

    client.post("/customer/checkout", json={
        "customer_id": customer_id, "items": [{"product_id": product_id, "quantity": 1}],
    })

    response = client.get(f"/products/{product_id}")
    assert response.json()["quantity_available"] == 0
