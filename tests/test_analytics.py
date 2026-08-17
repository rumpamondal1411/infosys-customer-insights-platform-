"""Tests for the centralized sales aggregation & baseline reporting engine."""
import os
from pathlib import Path

from fastapi.testclient import TestClient
from pytest import MonkeyPatch


def _setup_vendor_product(client, sku="SKU-A1"):
    # Register vendor
    reg = client.post(
        "/vendors/register",
        json={
            "business_name": "Analytics Vendor",
            "contact_person": "Sam",
            "email": f"{sku.lower()}@example.com",
            "password": "TestPass123",
            "phone": "+1-555-0200",
            "commission_rate": 0.10,
        }
    )

    print("Vendor:", reg.status_code, reg.json())

    vendor_id = reg.json()["id"]

    # Approve vendor
    client.patch(f"/vendors/{vendor_id}/approve", json={})

    # Create product
    product = client.post(
        "/products",
        json={
            "vendor_id": vendor_id,
            "sku": sku,
            "name": "Test Product",
            "price": 20.0,
            "initial_quantity": 100,
            "reorder_level": 10,
        }
    )

    print("Product:", product.status_code, product.json())

    product_id = product.json()["id"]

    return vendor_id, product_id
    


def test_sales_summary_empty(client: TestClient):
    response = client.get("/analytics/sales-summary")
    assert response.status_code == 200
    assert response.json()["total_revenue"] == 0.0


def test_sales_summary_after_transactions(client: TestClient):
    vendor_id, product_id = _setup_vendor_product(client)
    for _ in range(3):
        client.post("/transactions", json={
            "vendor_id": vendor_id, "product_id": product_id,
            "customer_id": 1, "quantity": 2,
        })
    response = client.get("/analytics/sales-summary")
    data = response.json()
    assert data["total_orders"] == 3
    assert data["total_units_sold"] == 6
    assert data["total_revenue"] == 120.0


def test_transaction_deducts_inventory(client: TestClient):
    vendor_id, product_id = _setup_vendor_product(client)
    client.post("/transactions", json={
        "vendor_id": vendor_id, "product_id": product_id, "customer_id": 1, "quantity": 10,
    })
    inv = client.get(f"/inventory/{product_id}").json()
    assert inv["quantity_available"] == 90


def test_revenue_by_vendor(client: TestClient):
    vendor_id, product_id = _setup_vendor_product(client)
    client.post("/transactions", json={
        "vendor_id": vendor_id, "product_id": product_id, "customer_id": 1, "quantity": 5,
    })
    response = client.get("/analytics/revenue-by-vendor")
    data = response.json()
    assert len(data) == 1
    assert data[0]["total_revenue"] == 100.0


def test_consistency_check_empty_marketplace(client: TestClient):
    """With no transactions, consistency should trivially be 100%."""
    response = client.get("/analytics/consistency-check")
    assert response.status_code == 200
    data = response.json()
    assert data["overall_consistency_pct"] == 100.0
    assert data["meets_threshold"] is True


def test_consistency_check_meets_threshold_after_sales(client: TestClient):
    """Milestone 1 criterion: >=98% transactional consistency."""
    vendor_id, product_id = _setup_vendor_product(client)
    for _ in range(5):
        client.post("/transactions", json={
            "vendor_id": vendor_id, "product_id": product_id, "customer_id": 1, "quantity": 2,
        })
    response = client.get("/analytics/consistency-check")
    data = response.json()
    assert data["overall_consistency_pct"] >= 98.0
    assert data["meets_threshold"] is True
    assert data["vendor_rollup_total"] == data["total_revenue"]
    assert data["category_rollup_total"] == data["total_revenue"]


def test_dashboard_page_renders(client: TestClient):
    """Milestone 1 criterion: dashboards successfully visualize metrics."""
    response = client.get("/dashboard")
    assert response.status_code == 200
    assert "text/html" in response.headers["content-type"]
    assert "Marketplace Dashboard" in response.text
    assert "vendorRevenueChart" in response.text  # chart canvas is present


def test_baseline_report_generation(client: TestClient, tmp_path: Path, monkeypatch: MonkeyPatch):
    vendor_id, product_id = _setup_vendor_product(client)
    client.post("/transactions", json={
        "vendor_id": vendor_id, "product_id": product_id, "customer_id": 1, "quantity": 3,
    })

    response = client.post("/analytics/reports/baseline")
    assert response.status_code == 200
    data = response.json()
    assert "summary" in data
    assert data["summary"]["total_orders"] == 1
    assert os.path.exists(data["_files"]["json"])
