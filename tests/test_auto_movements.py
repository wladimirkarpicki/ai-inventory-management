"""
P8: every real quantity change writes a stock_movements row in the same
transaction — creation records the initial stock, PATCH records the delta
with an optional reason, and a movement INSERT failure rolls the whole
product edit back.
"""

import pytest
from fastapi.testclient import TestClient

import main as main_module


@pytest.fixture()
def api():
    return TestClient(main_module.app)


@pytest.fixture()
def admin_api(api):
    response = api.post(
        "/api/auth/setup",
        json={"username": "admin", "password": "admin-pass-123"},
    )
    assert response.status_code == 200
    api.headers.update({"Authorization": f"Bearer {response.json()['access_token']}"})
    return api


def _create_brand_product(admin_api, name="Widget", qty=10):
    """Create a brand + product through the API; return (brand_id, product_id)."""
    brand_id = admin_api.post("/api/brands", json={"name": "Acme"}).json()["id"]
    product_id = admin_api.post(
        "/api/products",
        json={"brand_id": brand_id, "name": name, "price": 9.99, "quantity": qty},
    ).json()["id"]
    return brand_id, product_id


def _movements(admin_api):
    return admin_api.get("/api/movements", params={"limit": 100, "offset": 0}).json()


def test_create_product_records_initial_movement(api, admin_api):
    _brand_id, product_id = _create_brand_product(admin_api, qty=7)

    body = _movements(admin_api)

    assert body["total"] == 1
    m = body["items"][0]
    assert m["product_id"] == product_id
    assert m["in_out"] == "in"
    assert m["qty_delta"] == 7
    assert m["reason"] == "initial"


def test_create_product_zero_qty_records_nothing(api, admin_api):
    _create_brand_product(admin_api, qty=0)

    assert _movements(admin_api) == {"items": [], "total": 0}


def test_patch_decrease_records_out_with_payload_reason(api, admin_api):
    brand_id, product_id = _create_brand_product(admin_api, qty=10)

    response = admin_api.patch(
        f"/api/products/{product_id}",
        json={
            "brand_id": brand_id,
            "name": "Widget",
            "price": 9.99,
            "quantity": 8,
            "reason": "sale",
        },
    )

    assert response.status_code == 200
    body = _movements(admin_api)
    assert body["total"] == 2  # initial + the change
    m = body["items"][0]  # newest first
    assert m["product_id"] == product_id
    assert m["in_out"] == "out"
    assert m["qty_delta"] == -2
    assert m["reason"] == "sale"


def test_patch_increase_without_reason_uses_manual_edit(api, admin_api):
    brand_id, product_id = _create_brand_product(admin_api, qty=3)

    response = admin_api.patch(
        f"/api/products/{product_id}",
        json={"brand_id": brand_id, "name": "Widget", "price": 9.99, "quantity": 12},
    )

    assert response.status_code == 200
    m = _movements(admin_api)["items"][0]  # newest first
    assert m["in_out"] == "in"
    assert m["qty_delta"] == 9
    assert m["reason"] == "manual_edit"


def test_patch_without_quantity_change_records_nothing(api, admin_api):
    brand_id, product_id = _create_brand_product(admin_api, qty=5)

    response = admin_api.patch(
        f"/api/products/{product_id}",
        json={"brand_id": brand_id, "name": "Widget", "price": 19.99, "quantity": 5},
    )

    assert response.status_code == 200
    assert _movements(admin_api)["total"] == 1  # just the initial movement


def test_patch_reason_over_200_chars_is_rejected(api, admin_api):
    brand_id, product_id = _create_brand_product(admin_api, qty=10)

    response = admin_api.patch(
        f"/api/products/{product_id}",
        json={
            "brand_id": brand_id,
            "name": "Widget",
            "price": 9.99,
            "quantity": 8,
            "reason": "x" * 201,
        },
    )

    assert response.status_code == 422
    assert _movements(admin_api)["total"] == 1  # nothing recorded


def test_movement_failure_rolls_back_product_edit(api, admin_api, monkeypatch):
    brand_id, product_id = _create_brand_product(admin_api, qty=10)

    def boom(conn, product_id, delta, reason):
        raise RuntimeError("movement insert failed")

    monkeypatch.setattr(main_module, "_record_stock_movement", boom)
    lenient = TestClient(main_module.app, raise_server_exceptions=False)
    lenient.headers.update({"Authorization": admin_api.headers["Authorization"]})

    response = lenient.patch(
        f"/api/products/{product_id}",
        json={"brand_id": brand_id, "name": "Widget", "price": 9.99, "quantity": 4},
    )

    assert response.status_code == 500
    # the product edit was rolled back with the failed movement
    product = admin_api.get("/api/products", params={"search": "Widget"}).json()["items"][0]
    assert product["quantity"] == 10
    # and no movement row survived either
    assert _movements(admin_api)["total"] == 1  # just the initial movement
