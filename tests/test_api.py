"""
End-to-end tests for the FastAPI JSON backend in main.py.

They run against the same throwaway database as the Flask suite
(see conftest): DATABASE_NAME is pointed at it before any request,
so main.py connects to the test database transparently.
"""

import pytest
from fastapi.testclient import TestClient

import main as main_module

from conftest import ADMIN_PASSWORD, ADMIN_USERNAME, REGULAR_PASSWORD, REGULAR_USERNAME


@pytest.fixture()
def api():
    return TestClient(main_module.app)


def _bearer(token):
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture()
def admin_api(api):
    """
    A client authorized as the first account, which is an admin.
    """

    response = api.post(
        "/api/auth/setup",
        json={"username": ADMIN_USERNAME, "password": ADMIN_PASSWORD},
    )

    assert response.status_code == 200

    api.headers.update(_bearer(response.json()["access_token"]))

    return api


@pytest.fixture()
def user_api(api, admin_api):
    """
    A second client authorized as a regular user created by the admin.
    """

    response = admin_api.post(
        "/api/users",
        json={
            "username": REGULAR_USERNAME,
            "password": REGULAR_PASSWORD,
            "role": "user",
        },
    )

    assert response.status_code == 200

    # Fresh client for the regular user
    regular_client = TestClient(main_module.app)
    login_resp = regular_client.post(
        "/api/auth/login",
        json={"username": REGULAR_USERNAME, "password": REGULAR_PASSWORD},
    )
    regular_client.headers.update(_bearer(login_resp.json()["access_token"]))

    return regular_client


def _login(api, username, password):
    response = api.post(
        "/api/auth/login", json={"username": username, "password": password}
    )

    assert response.status_code == 200

    return response.json()["access_token"]


# ------------------------------------------------------------------ auth


def test_setup_creates_first_admin_and_then_closes(api):
    response = api.post(
        "/api/auth/setup",
        json={"username": ADMIN_USERNAME, "password": ADMIN_PASSWORD},
    )

    assert response.status_code == 200
    assert response.json()["user"]["role"] == "admin"

    response = api.post(
        "/api/auth/setup",
        json={"username": "second", "password": "second-pass-123"},
    )

    assert response.status_code == 400


def test_login_rejects_wrong_password(api, admin_api):
    response = api.post(
        "/api/auth/login",
        json={"username": ADMIN_USERNAME, "password": "wrong-pass-123"},
    )

    assert response.status_code == 401


def test_login_locks_after_five_failures(api, admin_api):
    for _ in range(5):
        response = api.post(
            "/api/auth/login",
            json={"username": ADMIN_USERNAME, "password": "wrong-pass-123"},
        )
        assert response.status_code == 401

    response = api.post(
        "/api/auth/login",
        json={"username": ADMIN_USERNAME, "password": ADMIN_PASSWORD},
    )

    assert response.status_code == 429


def test_rate_limit_only_affects_target_account(api, admin_api, user_api):
    for _ in range(5):
        api.post(
            "/api/auth/login",
            json={"username": REGULAR_USERNAME, "password": "wrong-pass-123"},
        )

    response = api.post(
        "/api/auth/login",
        json={"username": ADMIN_USERNAME, "password": ADMIN_PASSWORD},
    )

    assert response.status_code == 200


def test_me_requires_a_token(api):
    assert api.get("/api/auth/me").status_code == 401


def test_me_rejects_a_garbage_token(api):
    response = api.get("/api/auth/me", headers=_bearer("not-a-jwt"))

    assert response.status_code == 401


def test_me_returns_the_account(api, admin_api):
    response = admin_api.get("/api/auth/me")

    assert response.status_code == 200
    assert response.json()["username"] == ADMIN_USERNAME
    assert response.json()["role"] == "admin"


def test_token_of_deleted_account_is_rejected(api, admin_api, user_api):
    users = admin_api.get("/api/users").json()
    regular_id = next(u["id"] for u in users if u["username"] == REGULAR_USERNAME)

    assert admin_api.delete(f"/api/users/{regular_id}").status_code == 200

    response = user_api.get("/api/auth/me")

    assert response.status_code == 401


def test_self_service_password_change(api, admin_api):
    response = admin_api.post(
        "/api/auth/password",
        json={
            "current_password": ADMIN_PASSWORD,
            "password": "brand-new-pass-1",
        },
    )

    assert response.status_code == 200

    response = api.post(
        "/api/auth/login",
        json={"username": ADMIN_USERNAME, "password": ADMIN_PASSWORD},
    )

    assert response.status_code == 401


def test_password_change_requires_current_password(api, admin_api):
    response = admin_api.post(
        "/api/auth/password",
        json={"current_password": "wrong-pass-123", "password": "brand-new-pass-1"},
    )

    assert response.status_code == 400


# ------------------------------------------------------------------ users


def test_users_list_is_admin_only(api, admin_api, user_api):
    assert user_api.get("/api/users").status_code == 403
    assert admin_api.get("/api/users").status_code == 200


def test_create_user_requires_unique_username(api, admin_api):
    response = admin_api.post(
        "/api/users",
        json={
            "username": ADMIN_USERNAME,
            "password": "whatever-pass-1",
            "role": "user",
        },
    )

    assert response.status_code == 400


def test_cannot_demote_the_last_admin(api, admin_api):
    users = admin_api.get("/api/users").json()
    admin_id = next(u["id"] for u in users if u["role"] == "admin")

    response = admin_api.patch(f"/api/users/{admin_id}", json={"role": "user"})

    assert response.status_code == 400


def test_cannot_delete_yourself(api, admin_api):
    users = admin_api.get("/api/users").json()
    own_id = next(u["id"] for u in users if u["is_you"])

    response = admin_api.delete(f"/api/users/{own_id}")

    assert response.status_code == 400


def test_admin_reset_gives_access_with_the_new_password(api, admin_api):
    admin_api.post(
        "/api/users",
        json={
            "username": REGULAR_USERNAME,
            "password": REGULAR_PASSWORD,
            "role": "user",
        },
    )

    users = admin_api.get("/api/users").json()
    regular_id = next(u["id"] for u in users if u["username"] == REGULAR_USERNAME)

    response = admin_api.post(
        f"/api/users/{regular_id}/password", json={"password": "reset-pass-123"}
    )

    assert response.status_code == 200

    client = TestClient(main_module.app)
    response = client.post(
        "/api/auth/login",
        json={"username": REGULAR_USERNAME, "password": "reset-pass-123"},
    )

    assert response.status_code == 200


# ------------------------------------------------------------------ brands


def test_brand_crud_blocks_deleting_a_brand_with_products(api, admin_api):
    response = admin_api.post("/api/brands", json={"name": "Acme"})

    assert response.status_code == 200
    brand_id = response.json()["id"]

    assert (
        admin_api.post(
            "/api/brands", json={"name": "acme"}
        ).status_code
        == 400
    )

    product = admin_api.post(
        "/api/products",
        json={
            "brand_id": brand_id,
            "name": "Widget",
            "price": 9.99,
            "quantity": 3,
        },
    )

    assert product.status_code == 200

    response = admin_api.delete(f"/api/brands/{brand_id}")

    assert response.status_code == 400


# ------------------------------------------------------------------ products


def test_products_pagination_and_search(api, admin_api):
    brand_id = admin_api.post("/api/brands", json={"name": "Acme"}).json()["id"]

    for index in range(7):
        admin_api.post(
            "/api/products",
            json={
                "brand_id": brand_id,
                "name": f"Item {index}",
                "price": 1.0 + index,
                "quantity": index,
            },
        )

    response = admin_api.get("/api/products")

    assert response.status_code == 200
    body = response.json()

    assert body["total"] == 7
    assert body["pages"] == 2
    assert len(body["items"]) == 5

    response = admin_api.get("/api/products", params={"search": "Item 6"})

    assert response.json()["total"] == 1


def test_product_sorting_by_price_desc(api, admin_api):
    brand_id = admin_api.post("/api/brands", json={"name": "Acme"}).json()["id"]

    for price in (5.0, 1.0, 3.0):
        admin_api.post(
            "/api/products",
            json={
                "brand_id": brand_id,
                "name": f"P{price}",
                "price": price,
                "quantity": 1,
            },
        )

    response = admin_api.get(
        "/api/products", params={"sort": "price", "direction": "desc"}
    )

    prices = [item["price"] for item in response.json()["items"]]

    assert prices == [5.0, 3.0, 1.0]


def test_product_create_rejects_unknown_brand(api, admin_api):
    response = admin_api.post(
        "/api/products",
        json={
            "brand_id": 99999,
            "name": "Ghost",
            "price": 1.0,
            "quantity": 1,
        },
    )

    assert response.status_code == 400


def test_product_create_rejects_non_positive_price(api, admin_api):
    brand_id = admin_api.post("/api/brands", json={"name": "Acme"}).json()["id"]

    response = admin_api.post(
        "/api/products",
        json={"brand_id": brand_id, "name": "Free", "price": 0, "quantity": 1},
    )

    assert response.status_code == 422


def test_product_update_and_delete(api, admin_api):
    brand_id = admin_api.post("/api/brands", json={"name": "Acme"}).json()["id"]
    product_id = admin_api.post(
        "/api/products",
        json={
            "brand_id": brand_id,
            "name": "Widget",
            "price": 9.99,
            "quantity": 3,
        },
    ).json()["id"]

    response = admin_api.patch(
        f"/api/products/{product_id}",
        json={
            "brand_id": brand_id,
            "name": "Widget II",
            "price": 19.99,
            "quantity": 7,
        },
    )

    assert response.status_code == 200
    assert response.json()["name"] == "Widget II"
    assert response.json()["quantity"] == 7

    assert admin_api.delete(f"/api/products/{product_id}").status_code == 200
    assert admin_api.get("/api/products", params={"search": "Widget II"}).json()["total"] == 0


# ------------------------------------------------------------------ dashboard & export


def test_dashboard_stats_reflect_known_values(api, admin_api):
    brand_id = admin_api.post("/api/brands", json={"name": "Acme"}).json()["id"]
    admin_api.post(
        "/api/products",
        json={
            "brand_id": brand_id,
            "name": "Cheap",
            "price": 2.0,
            "quantity": 10,
        },
    )
    admin_api.post(
        "/api/products",
        json={
            "brand_id": brand_id,
            "name": "Pricy",
            "price": 3.0,
            "quantity": 2,
        },
    )

    response = admin_api.get("/api/dashboard/stats")

    assert response.status_code == 200
    stats = response.json()

    assert stats["products"] == 2
    assert stats["brands"] == 1
    assert stats["units_in_stock"] == 12
    assert stats["inventory_value"] == 26.0
    assert stats["low_stock"] == 1


def test_csv_export_requires_auth_and_has_header(api, admin_api):
    # admin_api shares the api client and has added a token to it,
    # so use a brand-new client for the unauthenticated check.
    fresh = TestClient(main_module.app)

    assert fresh.get("/api/export/products.csv").status_code == 401

    response = admin_api.get("/api/export/products.csv")

    assert response.status_code == 200
    assert response.text.splitlines()[0] == "ID,Brand,Name,Price,Quantity"


# ------------------------------------------------------------------ health


def test_health_is_open(api):
    assert api.get("/api/health").json() == {"status": "ok"}
