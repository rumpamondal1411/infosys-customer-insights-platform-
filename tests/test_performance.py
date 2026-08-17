"""
Milestone 4 — Performance tests.

These aren't load tests against a running server (that's a manual/Locust
job, see docs/DEPLOYMENT_GUIDE.md); they're fast, CI-friendly checks that
catch the two things that actually bite this codebase in practice:

1. An analytics/report endpoint accidentally regressing from a vectorised
   pandas groupby into a Python-level per-row loop as new fields get added
   (happened once already with vendor_performance during Milestone 2).
2. A response time that scales badly with data volume — checked by timing
   the same endpoint against a small dataset and a ~20x larger one and
   asserting the growth is roughly linear, not quadratic.

Thresholds are intentionally generous (this runs on shared CI runners, not
dedicated hardware) — the point is to catch a 10x+ regression, not to
enforce a strict SLA.
"""
import time


def _make_active_vendor(client, email):
    reg = client.post("/vendors/register", json={
        "business_name": f"Perf Vendor {email}",
        "contact_person": "Perf Tester",
        "email": email,
        "password": "TestPass123",
        "phone": "+1-555-0400",
        "commission_rate": 0.10,
    })
    vendor_id = reg.json()["id"]
    client.patch(f"/vendors/{vendor_id}/approve", json={})
    return vendor_id


def _seed_transactions(client, n_products: int, n_orders: int):
    vendor_id = _make_active_vendor(client, f"perf-vendor-{n_products}-{n_orders}@example.com")
    product_ids = []
    for i in range(n_products):
        resp = client.post("/products", json={
            "vendor_id": vendor_id, "sku": f"PERF-{n_products}-{n_orders}-{i}", "name": f"Perf Product {i}",
            "price": 15.0, "initial_quantity": 1000,
        })
        product_ids.append(resp.json()["id"])

    reg = client.post("/customer/register", json={
        "name": "Perf Buyer", "email": f"perf-buyer-{n_products}-{n_orders}@example.com",
        "password": "CustPass123",
    })
    customer_id = reg.json()["id"]
    client.put(f"/customer/{customer_id}/address", json={
        "address_line": "1 Perf Way",
        "city": "Testville",
        "state": "State",
        "pincode": "100001",
        "phone": "+1-555-0100",
    })

    for i in range(n_orders):
        product_id = product_ids[i % len(product_ids)]
        client.post("/customer/checkout", json={
            "customer_id": customer_id,
            "items": [{"product_id": product_id, "quantity": 1}],
        })


def test_sales_summary_responds_quickly_at_moderate_volume(client):
    _seed_transactions(client, n_products=10, n_orders=150)

    start = time.perf_counter()
    response = client.get("/analytics/sales-summary")
    elapsed = time.perf_counter() - start

    assert response.status_code == 200
    assert elapsed < 3.0, f"sales-summary took {elapsed:.2f}s for 150 orders — investigate for a non-vectorised regression"


def test_executive_summary_responds_quickly_at_moderate_volume(client):
    _seed_transactions(client, n_products=10, n_orders=150)

    start = time.perf_counter()
    response = client.get("/api/v1/executive/summary")
    elapsed = time.perf_counter() - start

    assert response.status_code == 200
    assert elapsed < 5.0, f"executive summary took {elapsed:.2f}s for 150 orders — investigate for an N+1 or non-vectorised path"


def test_vendor_performance_scales_roughly_linearly_with_order_volume(client):
    """
    Times the same endpoint at ~1x and ~5x order volume. A properly
    vectorised pandas groupby should scale close to linearly; a
    hidden per-row Python loop tends to show up as a much steeper curve.
    """
    _seed_transactions(client, n_products=5, n_orders=40)
    start_small = time.perf_counter()
    resp_small = client.get("/analytics/vendor-performance")
    elapsed_small = time.perf_counter() - start_small
    assert resp_small.status_code == 200

    _seed_transactions(client, n_products=5, n_orders=200)
    start_large = time.perf_counter()
    resp_large = client.get("/analytics/vendor-performance")
    elapsed_large = time.perf_counter() - start_large
    assert resp_large.status_code == 200

    # Generous ceiling: allow up to ~15x slowdown for ~6x the data before
    # flagging a likely non-linear regression (avoids CI flakiness on
    # shared/slow runners while still catching real quadratic behaviour).
    assert elapsed_large < max(elapsed_small * 15, 2.0), (
        f"vendor-performance scaled from {elapsed_small:.3f}s to {elapsed_large:.3f}s "
        "for a ~6x increase in orders — check for non-linear behaviour"
    )


def test_etl_pipeline_completes_within_budget_at_moderate_volume(client):
    _seed_transactions(client, n_products=10, n_orders=150)

    start = time.perf_counter()
    response = client.post("/api/v1/etl/run")
    elapsed = time.perf_counter() - start

    assert response.status_code == 200
    assert response.json()["status"] == "success"
    assert elapsed < 5.0, f"ETL pipeline took {elapsed:.2f}s for 150 orders — investigate for a regression"
