"""Milestone 4 — tests for app/services/executive_report_service.py and
app/routers/executive_reports.py."""
import os

from app.services import executive_report_service


def _make_active_vendor(client, email="exec-vendor@example.com"):
    reg = client.post("/vendors/register", json={
        "business_name": "Executive Test Vendor",
        "contact_person": "Exec Tester",
        "email": email,
        "password": "TestPass123",
        "phone": "+1-555-0600",
        "commission_rate": 0.10,
    })
    vendor_id = reg.json()["id"]
    client.patch(f"/vendors/{vendor_id}/approve", json={})
    return vendor_id


def _make_product(client, vendor_id, sku="SKU-EXEC-1", price=60.0, qty=15):
    resp = client.post("/products", json={
        "vendor_id": vendor_id, "sku": sku, "name": "Executive Test Product",
        "price": price, "initial_quantity": qty,
    })
    return resp.json()["id"]


def _make_customer(client, email="exec-buyer@example.com"):
    reg = client.post("/customer/register", json={
        "name": "Executive Test Customer", "email": email, "password": "CustPass123",
    })
    customer_id = reg.json()["id"]
    client.put(f"/customer/{customer_id}/address", json={
        "address_line": "1 Executive Way",
        "city": "Testville",
        "state": "State",
        "pincode": "100001",
        "phone": "+1-555-0100",
    })
    return customer_id


def test_executive_summary_empty_db_returns_zeroed_kpis(db_session):
    summary = executive_report_service.executive_summary(db_session)
    assert summary["kpis"]["total_revenue"] == 0
    assert summary["kpis"]["total_orders"] == 0
    assert summary["top_vendor"] is None
    assert summary["top_products"] == []


def test_executive_summary_reflects_seeded_orders(client):
    vendor_id = _make_active_vendor(client)
    product_id = _make_product(client, vendor_id)
    customer_id = _make_customer(client)

    client.post("/customer/checkout", json={
        "customer_id": customer_id,
        "items": [{"product_id": product_id, "quantity": 2}],
    })

    response = client.get("/api/v1/executive/summary")
    assert response.status_code == 200
    body = response.json()
    assert body["kpis"]["total_revenue"] >= 120.0
    assert body["kpis"]["total_orders"] >= 1
    assert body["top_vendor"]["business_name"] == "Executive Test Vendor"


def test_executive_summary_rejects_out_of_range_period(client):
    response = client.get("/api/v1/executive/summary?period_days=0")
    assert response.status_code == 422

    response = client.get("/api/v1/executive/summary?period_days=9999")
    assert response.status_code == 422


def test_kpi_trend_empty_db_returns_empty_list(client):
    response = client.get("/api/v1/executive/kpi-trend")
    assert response.status_code == 200
    assert response.json() == []


def test_kpi_trend_reflects_seeded_orders(client):
    vendor_id = _make_active_vendor(client, email="exec-vendor-trend@example.com")
    product_id = _make_product(client, vendor_id, sku="SKU-EXEC-TREND")
    customer_id = _make_customer(client, email="exec-buyer-trend@example.com")

    client.post("/customer/checkout", json={
        "customer_id": customer_id,
        "items": [{"product_id": product_id, "quantity": 1}],
    })

    response = client.get("/api/v1/executive/kpi-trend?months=3")
    assert response.status_code == 200
    trend = response.json()
    assert len(trend) >= 1
    assert "month" in trend[0] and "revenue" in trend[0]


def test_export_executive_workbook_writes_xlsx_file(db_session):
    path = executive_report_service.export_executive_workbook(db_session)
    assert os.path.exists(path)
    assert path.endswith(".xlsx")


def test_export_executive_report_endpoint_returns_excel_file(client):
    vendor_id = _make_active_vendor(client, email="exec-vendor-export@example.com")
    product_id = _make_product(client, vendor_id, sku="SKU-EXEC-EXPORT")
    customer_id = _make_customer(client, email="exec-buyer-export@example.com")
    client.post("/customer/checkout", json={
        "customer_id": customer_id,
        "items": [{"product_id": product_id, "quantity": 1}],
    })

    response = client.get("/api/v1/executive/export")
    assert response.status_code == 200
    assert response.headers["content-type"].startswith(
        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )
