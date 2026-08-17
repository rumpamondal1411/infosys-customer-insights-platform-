"""Tests for the Product & Inventory Analytics Engine module."""


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


def test_create_product_requires_active_vendor(client):
    reg = client.post("/vendors/register", json={
        "business_name": "Pending Co",
        "contact_person": "Jane",
        "email": "pending@example.com",
        "phone": "9876543210",
    })
    vendor_id = reg.json()["id"]

    response = client.post("/products", json={
        "vendor_id": vendor_id, "sku": "SKU-1", "name": "Widget", "price": 9.99,
    })
    assert response.status_code == 400


def test_create_product_with_inventory(client):
    vendor_id = _make_active_vendor(client)
    response = client.post("/products", json={
        "vendor_id": vendor_id, "sku": "SKU-100", "name": "Bluetooth Speaker",
        "price": 49.99, "initial_quantity": 25, "reorder_level": 5,
    })
    assert response.status_code == 201
    product_id = response.json()["id"]

    inv = client.get(f"/inventory/{product_id}")
    assert inv.status_code == 200
    assert inv.json()["quantity_available"] == 25


def test_duplicate_sku_rejected(client):
    vendor_id = _make_active_vendor(client)
    client.post("/products", json={
        "vendor_id": vendor_id, "sku": "SKU-DUP", "name": "Item A", "price": 5.0,
    })
    response = client.post("/products", json={
        "vendor_id": vendor_id, "sku": "SKU-DUP", "name": "Item B", "price": 6.0,
    })
    assert response.status_code == 400


def test_low_stock_alert(client):
    vendor_id = _make_active_vendor(client)
    client.post("/products", json={
        "vendor_id": vendor_id, "sku": "SKU-LOW", "name": "Low Stock Item",
        "price": 15.0, "initial_quantity": 2, "reorder_level": 10,
    })
    response = client.get("/inventory/alerts/low-stock")
    assert response.status_code == 200
    alerts = response.json()
    assert len(alerts) == 1
    assert alerts[0]["sku"] == "SKU-LOW"


def test_restock_increases_quantity(client):
    vendor_id = _make_active_vendor(client)
    p = client.post("/products", json={
        "vendor_id": vendor_id, "sku": "SKU-RESTOCK", "name": "Item",
        "price": 10.0, "initial_quantity": 5,
    }).json()

    response = client.post(f"/inventory/{p['id']}/restock", json={"quantity": 20})
    assert response.json()["quantity_available"] == 25


def _make_product(client, sku="SKU-IMG"):
    vendor_id = _make_active_vendor(client, email=f"{sku.lower()}@example.com")
    p = client.post("/products", json={
        "vendor_id": vendor_id, "sku": sku, "name": "Image Test Product", "price": 25.0,
    }).json()
    return p["id"]


def _tiny_png_bytes():
    # A minimal valid 1x1 transparent PNG, used so we upload real image bytes
    # rather than an arbitrary blob.
    import base64
    return base64.b64decode(
        "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNk+A8AAQUBAScY42YAAAAASUVORK5CYII="
    )


def test_product_has_no_image_by_default(client):
    product_id = _make_product(client)
    response = client.get(f"/products/{product_id}")
    assert response.json()["image_url"] is None


def test_upload_product_image_success(client):
    product_id = _make_product(client)
    files = {"file": ("photo.png", _tiny_png_bytes(), "image/png")}
    response = client.post(f"/products/{product_id}/image", files=files)
    assert response.status_code == 200
    data = response.json()
    assert data["image_url"] == f"/static/uploads/products/{product_id}.png"

    # And the file actually landed on disk
    import os
    assert os.path.exists("app" + data["image_url"])


def test_upload_product_image_rejects_bad_type(client):
    product_id = _make_product(client)
    files = {"file": ("notes.txt", b"just some text", "text/plain")}
    response = client.post(f"/products/{product_id}/image", files=files)
    assert response.status_code == 400
    assert "JPG, PNG" in response.json()["detail"]


def test_upload_product_image_rejects_oversized_file(client):
    product_id = _make_product(client)
    oversized = b"0" * (5 * 1024 * 1024 + 1)
    files = {"file": ("big.png", oversized, "image/png")}
    response = client.post(f"/products/{product_id}/image", files=files)
    assert response.status_code == 400
    assert "5MB" in response.json()["detail"]


def test_reupload_replaces_previous_image(client):
    product_id = _make_product(client)
    files_png = {"file": ("photo.png", _tiny_png_bytes(), "image/png")}
    client.post(f"/products/{product_id}/image", files=files_png)

    files_jpg = {"file": ("photo.jpg", _tiny_png_bytes(), "image/jpeg")}
    response = client.post(f"/products/{product_id}/image", files=files_jpg)
    data = response.json()
    assert data["image_url"] == f"/static/uploads/products/{product_id}.jpg"

    # Old .png file should have been cleaned up, not left orphaned
    import os
    assert not os.path.exists(f"app/static/uploads/products/{product_id}.png")


def test_delete_product_image(client):
    product_id = _make_product(client)
    files = {"file": ("photo.png", _tiny_png_bytes(), "image/png")}
    client.post(f"/products/{product_id}/image", files=files)

    response = client.delete(f"/products/{product_id}/image")
    assert response.status_code == 200
    assert response.json()["image_url"] is None

    import os
    assert not os.path.exists(f"app/static/uploads/products/{product_id}.png")


def test_product_list_includes_image_url(client):
    product_id = _make_product(client)
    files = {"file": ("photo.png", _tiny_png_bytes(), "image/png")}
    client.post(f"/products/{product_id}/image", files=files)

    response = client.get(f"/products/{product_id}")
    assert response.json()["image_url"] == f"/static/uploads/products/{product_id}.png"
