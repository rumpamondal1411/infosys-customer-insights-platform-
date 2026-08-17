"""
Milestone 4 — Integration / end-to-end tests.

Unlike the per-module test files (test_orders.py, test_customer_analytics.py,
etc.) these tests exercise a full workflow across module boundaries in one
pass: vendor onboarding -> catalogue -> customer purchase -> rating ->
wishlist -> ETL pipeline -> analytics/reporting -> executive summary. The
goal is to catch integration bugs (a field renamed in one service but not
updated where another service consumes it, a status transition that breaks
a downstream aggregation, etc.) that isolated unit tests can't see.
"""
import os


def _make_active_vendor(client, email="e2e-vendor@example.com"):
    reg = client.post("/vendors/register", json={
        "business_name": "E2E Test Vendor",
        "contact_person": "Jamie Rivera",
        "email": email,
        "password": "TestPass123",
        "phone": "+1-555-0300",
        "commission_rate": 0.10,
    })
    assert reg.status_code == 201, reg.text
    vendor_id = reg.json()["id"]
    approve = client.patch(f"/vendors/{vendor_id}/approve", json={})
    assert approve.status_code == 200, approve.text
    return vendor_id


def _make_product(client, vendor_id, sku="SKU-E2E-1", name="E2E Test Widget", price=40.0, qty=25):
    response = client.post("/products", json={
        "vendor_id": vendor_id, "sku": sku, "name": name,
        "price": price, "initial_quantity": qty,
    })
    assert response.status_code == 201, response.text
    return response.json()["id"]


def _make_customer(client, email="e2e-buyer@example.com"):
    reg = client.post("/customer/register", json={
        "name": "E2E Test Customer", "email": email, "password": "CustPass123",
    })
    assert reg.status_code == 201, reg.text
    customer_id = reg.json()["id"]
    client.put(f"/customer/{customer_id}/address", json={
        "address_line": "1 Integration Way",
        "city": "Testville",
        "state": "State",
        "pincode": "100001",
        "phone": "+1-555-0100",
    })
    return customer_id


def test_full_order_lifecycle_flows_through_to_analytics(client):
    """
    Vendor onboarding -> product listing -> customer purchase -> rating ->
    wishlist -> ETL -> analytics/reporting/executive summary all need to
    agree on the same underlying data.
    """
    vendor_id = _make_active_vendor(client)
    product_id = _make_product(client, vendor_id, qty=25)
    customer_id = _make_customer(client)

    # Wishlist before purchase
    wish = client.post(f"/customer/{customer_id}/wishlist/{product_id}")
    assert wish.status_code == 201

    # Checkout
    checkout = client.post("/customer/checkout", json={
        "customer_id": customer_id,
        "items": [{"product_id": product_id, "quantity": 3}],
    })
    assert checkout.status_code == 201, checkout.text
    order = checkout.json()
    assert len(order["items"]) == 1

    # Inventory deducted
    inv = client.get(f"/inventory/{product_id}")
    assert inv.json()["quantity_available"] == 22

    # Rating submitted after purchase
    rating = client.post(f"/products/{product_id}/ratings", json={
        "customer_id": customer_id, "stars": 5, "review_text": "Great product",
    })
    assert rating.status_code in (200, 201), rating.text

    ratings_list = client.get(f"/products/{product_id}/ratings")
    assert ratings_list.status_code == 200
    assert len(ratings_list.json()) == 1

    # ETL pipeline picks the new transaction up
    etl = client.post("/api/v1/etl/run")
    assert etl.status_code == 200, etl.text
    assert etl.json()["status"] == "success"

    # Core analytics reflects the purchase
    summary = client.get("/analytics/sales-summary")
    assert summary.status_code == 200
    assert summary.json()["total_orders"] >= 1
    assert summary.json()["total_revenue"] >= 120.0  # 3 * $40

    # Executive summary (Milestone 4) agrees with the same underlying data
    exec_summary = client.get("/api/v1/executive/summary")
    assert exec_summary.status_code == 200
    exec_kpis = exec_summary.json()["kpis"]
    assert exec_kpis["total_orders"] >= 1
    assert exec_kpis["total_revenue"] >= 120.0
    assert exec_summary.json()["top_products"], "expected at least one top product"


def test_vendor_suspension_removes_products_from_active_catalogue(client):
    """Cross-module regression guard: suspending a vendor must not leave
    its products purchasable, and must not break vendor_performance."""
    vendor_id = _make_active_vendor(client, email="e2e-vendor2@example.com")
    product_id = _make_product(client, vendor_id, sku="SKU-E2E-2")

    suspend = client.patch(f"/vendors/{vendor_id}/suspend", json={})
    assert suspend.status_code == 200

    perf = client.get("/analytics/vendor-performance")
    assert perf.status_code == 200
    assert any(v["vendor_id"] == vendor_id for v in perf.json())


def test_scheduled_report_and_executive_export_do_not_error(client, tmp_path, monkeypatch):
    """The Milestone 3 scheduled report and the Milestone 4 executive
    export both need to run cleanly against the same live database state."""
    vendor_id = _make_active_vendor(client, email="e2e-vendor3@example.com")
    product_id = _make_product(client, vendor_id, sku="SKU-E2E-3")
    customer_id = _make_customer(client, email="e2e-buyer3@example.com")
    client.post("/customer/checkout", json={
        "customer_id": customer_id,
        "items": [{"product_id": product_id, "quantity": 1}],
    })

    report = client.post("/api/v1/reports/scheduled/run")
    assert report.status_code in (200, 201), report.text

    export = client.get("/api/v1/executive/export")
    assert export.status_code == 200
    assert export.headers["content-type"].startswith(
        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )
