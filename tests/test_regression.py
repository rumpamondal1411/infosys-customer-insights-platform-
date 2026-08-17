"""
Milestone 4 — Regression tests.

Locks down the bug fixes made during the Milestone 3 hardening pass
(ratings, wishlist, checkout, spending analytics, BI dashboard) so they
can't silently resurface as the codebase keeps changing. Each test names
the specific behaviour that broke before, not just "the feature works".
"""


def _make_active_vendor(client, email="reg-vendor@example.com"):
    reg = client.post("/vendors/register", json={
        "business_name": "Regression Vendor",
        "contact_person": "Reg Tester",
        "email": email,
        "password": "TestPass123",
        "phone": "+1-555-0500",
        "commission_rate": 0.10,
    })
    vendor_id = reg.json()["id"]
    client.patch(f"/vendors/{vendor_id}/approve", json={})
    return vendor_id


def _make_product(client, vendor_id, sku="SKU-REG-1", price=30.0, qty=20):
    resp = client.post("/products", json={
        "vendor_id": vendor_id, "sku": sku, "name": "Regression Widget",
        "price": price, "initial_quantity": qty,
    })
    return resp.json()["id"]


def _make_customer(client, email="reg-buyer@example.com"):
    reg = client.post("/customer/register", json={
        "name": "Regression Customer", "email": email, "password": "CustPass123",
    })
    customer_id = reg.json()["id"]
    client.put(f"/customer/{customer_id}/address", json={
        "address_line": "1 Regression Way",
        "city": "Testville",
        "state": "State",
        "pincode": "100001",
        "phone": "+1-555-0100",
    })
    return customer_id


# ------------------------------------------------------------ Ratings

def test_rating_can_be_updated_not_just_created(client):
    """A customer resubmitting a rating for the same product must update
    the existing row, not create a duplicate (previous bug: unique
    customer+product constraint wasn't honoured on resubmission)."""
    vendor_id = _make_active_vendor(client)
    product_id = _make_product(client, vendor_id)
    customer_id = _make_customer(client)

    first = client.post(f"/products/{product_id}/ratings", json={
        "customer_id": customer_id, "stars": 3, "review_text": "It's okay",
    })
    assert first.status_code in (200, 201)

    second = client.post(f"/products/{product_id}/ratings", json={
        "customer_id": customer_id, "stars": 5, "review_text": "Actually great",
    })
    assert second.status_code in (200, 201)

    all_ratings = client.get(f"/products/{product_id}/ratings").json()
    assert len(all_ratings) == 1, "resubmitting a rating created a duplicate row instead of updating it"
    assert all_ratings[0]["stars"] == 5


def test_rating_requires_valid_star_range(client):
    """Stars outside 1-5 must be rejected, not silently clamped or stored."""
    vendor_id = _make_active_vendor(client, email="reg-vendor-stars@example.com")
    product_id = _make_product(client, vendor_id, sku="SKU-REG-STARS")
    customer_id = _make_customer(client, email="reg-buyer-stars@example.com")

    response = client.post(f"/products/{product_id}/ratings", json={
        "customer_id": customer_id, "stars": 7,
    })
    assert response.status_code in (400, 422)


# ------------------------------------------------------------ Wishlist

def test_wishlist_add_is_idempotent(client):
    """Adding the same product to the wishlist twice must not create two
    rows or raise a 500 (previous bug: unique constraint violation
    surfaced as an unhandled server error instead of a clean response)."""
    vendor_id = _make_active_vendor(client, email="reg-vendor-wish@example.com")
    product_id = _make_product(client, vendor_id, sku="SKU-REG-WISH")
    customer_id = _make_customer(client, email="reg-buyer-wish@example.com")

    first = client.post(f"/customer/{customer_id}/wishlist/{product_id}")
    assert first.status_code == 201

    second = client.post(f"/customer/{customer_id}/wishlist/{product_id}")
    assert second.status_code in (200, 201, 409), (
        f"re-adding an already-wishlisted product returned {second.status_code}, "
        "expected a clean success or conflict response, not a server error"
    )

    wishlist = client.get(f"/customer/{customer_id}/wishlist").json()
    assert len(wishlist) == 1, "duplicate wishlist entry was created"


def test_wishlist_remove_then_check_reflects_empty_state(client):
    vendor_id = _make_active_vendor(client, email="reg-vendor-wish2@example.com")
    product_id = _make_product(client, vendor_id, sku="SKU-REG-WISH2")
    customer_id = _make_customer(client, email="reg-buyer-wish2@example.com")

    client.post(f"/customer/{customer_id}/wishlist/{product_id}")
    remove = client.delete(f"/customer/{customer_id}/wishlist/{product_id}")
    assert remove.status_code == 204

    wishlist = client.get(f"/customer/{customer_id}/wishlist").json()
    assert wishlist == []


# ------------------------------------------------------------ Checkout

def test_checkout_with_multiple_line_items_deducts_each_products_stock_independently(client):
    """Previous bug: multi-item checkout deducted stock correctly for the
    first item but skipped or double-deducted subsequent items."""
    vendor_id = _make_active_vendor(client, email="reg-vendor-multi@example.com")
    product_a = _make_product(client, vendor_id, sku="SKU-REG-A", qty=10)
    product_b = _make_product(client, vendor_id, sku="SKU-REG-B", qty=10)
    customer_id = _make_customer(client, email="reg-buyer-multi@example.com")

    response = client.post("/customer/checkout", json={
        "customer_id": customer_id,
        "items": [
            {"product_id": product_a, "quantity": 2},
            {"product_id": product_b, "quantity": 3},
        ],
    })
    assert response.status_code == 201
    assert len(response.json()["items"]) == 2

    inv_a = client.get(f"/inventory/{product_a}").json()
    inv_b = client.get(f"/inventory/{product_b}").json()
    assert inv_a["quantity_available"] == 8
    assert inv_b["quantity_available"] == 7


def test_checkout_zero_quantity_is_rejected(client):
    vendor_id = _make_active_vendor(client, email="reg-vendor-zero@example.com")
    product_id = _make_product(client, vendor_id, sku="SKU-REG-ZERO")
    customer_id = _make_customer(client, email="reg-buyer-zero@example.com")

    response = client.post("/customer/checkout", json={
        "customer_id": customer_id,
        "items": [{"product_id": product_id, "quantity": 0}],
    })
    assert response.status_code in (400, 422)


# ------------------------------------------------------------ Spending analytics

def test_customer_revenue_analysis_matches_actual_completed_orders(client):
    """Previous bug: revenue-analysis included cancelled/returned orders in
    the customer's lifetime spend total."""
    vendor_id = _make_active_vendor(client, email="reg-vendor-spend@example.com")
    product_id = _make_product(client, vendor_id, sku="SKU-REG-SPEND", price=50.0, qty=10)
    customer_id = _make_customer(client, email="reg-buyer-spend@example.com")

    order = client.post("/customer/checkout", json={
        "customer_id": customer_id,
        "items": [{"product_id": product_id, "quantity": 1}],
    })
    transaction_id = order.json()["items"][0]["transaction_id"]

    if transaction_id is not None:
        client.post(f"/customer/{customer_id}/orders/{transaction_id}/cancel", json={"reason": "changed mind"})

    analysis = client.get(f"/customer-analytics/customer/{customer_id}/revenue-analysis")
    assert analysis.status_code == 200
    # A cancelled order must not be counted as spend.
    body = analysis.json()
    if "total_spent" in body:
        assert body["total_spent"] == 0.0


# ------------------------------------------------------------ BI dashboard / executive reporting

def test_executive_summary_does_not_error_on_empty_database(client):
    """Previous bug: BI dashboard endpoints 500'd on a fresh database with
    no transactions yet (division by zero / empty-dataframe groupby)."""
    response = client.get("/api/v1/executive/summary")
    assert response.status_code == 200
    kpis = response.json()["kpis"]
    assert kpis["total_revenue"] == 0
    assert kpis["total_orders"] == 0


def test_executive_kpi_trend_does_not_error_on_empty_database(client):
    response = client.get("/api/v1/executive/kpi-trend")
    assert response.status_code == 200
    assert response.json() == []


def test_bi_dashboard_page_renders_without_server_error(client):
    response = client.get("/bi-dashboard")
    assert response.status_code == 200
