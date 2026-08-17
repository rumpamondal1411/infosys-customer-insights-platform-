"""Tests for the Vendor Management & Marketplace Onboarding module."""


def _vendor_payload(email="vendor1@example.com"):
    return {
        "business_name": "Test Traders Inc.",
        "contact_person": "Jane Doe",
        "email": email,
        "password": "TestPass123",
        "phone": "+1-555-0100",
        "address": "123 Market St",
        "country": "USA",
        "commission_rate": 0.12,
        "primary_category": "Electronics",
    }


def test_register_vendor(client):
    response = client.post("/vendors/register", json=_vendor_payload())
    assert response.status_code == 201
    data = response.json()
    assert data["business_name"] == "Test Traders Inc."
    assert data["status"] == "pending"
    assert data["verification_status"] == "unverified"


def test_register_duplicate_email_rejected(client):
    client.post("/vendors/register", json=_vendor_payload())
    response = client.post("/vendors/register", json=_vendor_payload())
    assert response.status_code == 400


def test_vendor_onboarding_workflow(client):
    reg = client.post("/vendors/register", json=_vendor_payload())
    vendor_id = reg.json()["id"]

    submit = client.post(f"/vendors/{vendor_id}/submit-for-verification")
    assert submit.json()["verification_status"] == "in_review"

    approve = client.patch(f"/vendors/{vendor_id}/approve", json={"reason": "Docs verified"})
    assert approve.status_code == 200
    assert approve.json()["status"] == "active"
    assert approve.json()["verification_status"] == "verified"


def test_suspend_and_reactivate_vendor(client):
    reg = client.post("/vendors/register", json=_vendor_payload())
    vendor_id = reg.json()["id"]
    client.patch(f"/vendors/{vendor_id}/approve", json={})

    suspend = client.patch(f"/vendors/{vendor_id}/suspend", json={"reason": "policy violation"})
    assert suspend.json()["status"] == "suspended"

    reactivate = client.patch(f"/vendors/{vendor_id}/reactivate")
    assert reactivate.json()["status"] == "active"


def test_cannot_suspend_pending_vendor(client):
    reg = client.post("/vendors/register", json=_vendor_payload())
    vendor_id = reg.json()["id"]
    response = client.patch(f"/vendors/{vendor_id}/suspend", json={})
    assert response.status_code == 400


def test_list_vendors_filter_by_status(client):
    client.post("/vendors/register", json=_vendor_payload("a@example.com"))
    client.post("/vendors/register", json=_vendor_payload("b@example.com"))
    response = client.get("/vendors", params={"status": "pending"})
    assert response.status_code == 200
    assert len(response.json()) == 2


def test_get_nonexistent_vendor_404(client):
    response = client.get("/vendors/9999")
    assert response.status_code == 404


def test_invalid_phone_rejected_cleanly(client):
    """Milestone 1: invalid registrations must fail with 400, never crash (500)."""
    payload = _vendor_payload("badphone@example.com")
    payload["phone"] = "not-a-phone!!"
    response = client.post("/vendors/register", json=payload)
    assert response.status_code == 400
    assert "phone" in response.json()["detail"].lower()


def test_duplicate_tax_id_rejected_cleanly(client):
    """Milestone 1: duplicate tax_id must fail with 400, never crash (500)."""
    payload_a = _vendor_payload("vendora@example.com")
    payload_a["tax_id"] = "TAX-DUP-001"
    client.post("/vendors/register", json=payload_a)

    payload_b = _vendor_payload("vendorb@example.com")
    payload_b["tax_id"] = "TAX-DUP-001"
    response = client.post("/vendors/register", json=payload_b)
    assert response.status_code == 400


def test_blank_business_name_rejected(client):
    payload = _vendor_payload("blankname@example.com")
    payload["business_name"] = "   "
    response = client.post("/vendors/register", json=payload)
    assert response.status_code == 400


def test_invalid_commission_rate_rejected_by_schema(client):
    payload = _vendor_payload("badcommission@example.com")
    payload["commission_rate"] = 1.5  # outside 0-1, caught by Pydantic Field constraint
    response = client.post("/vendors/register", json=payload)
    assert response.status_code == 422
