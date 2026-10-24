"""
End-to-end tests for the FastAPI JSON backend in main.py.

They run against the same throwaway database as the Flask suite
(see conftest): DATABASE_NAME is pointed at it before any request,
so main.py connects to the test database transparently.
"""

import pytest
from conftest import ADMIN_PASSWORD, ADMIN_USERNAME, REGULAR_PASSWORD, REGULAR_USERNAME
from fastapi.testclient import TestClient

import main as main_module


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
    response = api.post("/api/auth/login", json={"username": username, "password": password})

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

    assert admin_api.post("/api/brands", json={"name": "acme"}).status_code == 400

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

    for index in range(32):
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

    assert body["total"] == 32
    assert body["pages"] == 3  # PAGE_SIZE = 15
    assert len(body["items"]) == 15

    tail = admin_api.get("/api/products", params={"page": 3})
    assert tail.status_code == 200
    assert len(tail.json()["items"]) == 2

    response = admin_api.get("/api/products", params={"search": "Item 31"})

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

    response = admin_api.get("/api/products", params={"sort": "price", "direction": "desc"})

    prices = [item["price"] for item in response.json()["items"]]

    assert prices == [5.0, 3.0, 1.0]


def test_products_low_stock_only_filter(api, admin_api):
    brand_id = admin_api.post("/api/brands", json={"name": "FilterCo"}).json()["id"]

    def make(name, qty, reorder_point):
        return admin_api.post(
            "/api/products",
            json={
                "brand_id": brand_id,
                "name": name,
                "price": 1.0,
                "quantity": qty,
                "reorder_point": reorder_point,
            },
        )

    make("Below", qty=2, reorder_point=10)
    make("Above", qty=50, reorder_point=20)
    make("Equal", qty=10, reorder_point=10)
    make("NoStock", qty=0, reorder_point=10)

    # Only strictly-below-reorder-point products, NULL quantities excluded.
    response = admin_api.get("/api/products", params={"low_stock_only": "true"})

    assert response.status_code == 200
    names = [i["name"] for i in response.json()["items"]]
    assert names == ["Below", "NoStock"]

    # The new sort key rides the same validated SORT_COLUMNS allowlist.
    response = admin_api.get(
        "/api/products", params={"sort": "reorder_point", "direction": "desc"}
    )
    rps = [i["reorder_point"] for i in response.json()["items"]]
    assert rps == [20, 10, 10, 10]


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


def test_ready_reports_database_up(api):
    response = api.get("/api/ready")
    assert response.status_code == 200
    assert response.json() == {"status": "ready", "database": "up"}


def test_metrics_exposed(api):
    response = api.get("/metrics")
    assert response.status_code == 200
    assert "http_request" in response.text


# ------------------------------------------------------------------ product uniqueness (P18)


def test_create_product_duplicate_name_same_brand_rejected(api, admin_api):
    brand_id = admin_api.post("/api/brands", json={"name": "DedupeCo"}).json()["id"]

    first = admin_api.post(
        "/api/products",
        json={"brand_id": brand_id, "name": "Widget", "price": 1.0, "quantity": 1},
    )
    assert first.status_code == 200

    # Same brand, same name in different case → 400, not a duplicate row.
    dup = admin_api.post(
        "/api/products",
        json={"brand_id": brand_id, "name": "WIDGET", "price": 2.0, "quantity": 2},
    )
    assert dup.status_code == 400

    # Same name under a different brand is a distinct product → allowed.
    other_brand = admin_api.post("/api/brands", json={"name": "DedupeOther"}).json()["id"]
    ok = admin_api.post(
        "/api/products",
        json={"brand_id": other_brand, "name": "Widget", "price": 2.0, "quantity": 2},
    )
    assert ok.status_code == 200


def test_update_product_rename_into_duplicate_rejected(api, admin_api):
    brand_id = admin_api.post("/api/brands", json={"name": "RenameCo"}).json()["id"]
    admin_api.post(
        "/api/products",
        json={"brand_id": brand_id, "name": "Alpha", "price": 1.0, "quantity": 1},
    )
    beta_id = admin_api.post(
        "/api/products",
        json={"brand_id": brand_id, "name": "Beta", "price": 1.0, "quantity": 1},
    ).json()["id"]

    # Renaming Beta into (case-insensitive) Alpha collides → 400.
    dup = admin_api.patch(
        f"/api/products/{beta_id}",
        json={
            "brand_id": brand_id,
            "name": "ALPHA",
            "price": 1.0,
            "quantity": 1,
            "reason": "manual_edit",
        },
    )
    assert dup.status_code == 400

    # Keeping its own name (only price changes) is fine.
    keep = admin_api.patch(
        f"/api/products/{beta_id}",
        json={"brand_id": brand_id, "name": "Beta", "price": 1.5, "quantity": 1},
    )
    assert keep.status_code == 200


def test_products_unique_brand_lower_name_enforced_by_db(db_connection):
    import psycopg.errors

    with db_connection.cursor() as cur:
        cur.execute("INSERT INTO brands (name) VALUES ('IdxCo') RETURNING id")
        brand_id = cur.fetchone()[0]
        cur.execute(
            "INSERT INTO products (brand_id, name, price, quantity) "
            "VALUES (%s, 'Same', 1, 1)",
            (brand_id,),
        )
    db_connection.commit()

    # schema.sql carries the unique index — a direct duplicate INSERT
    # must fail at the database level.
    with pytest.raises(psycopg.errors.UniqueViolation):
        with db_connection.cursor() as cur:
            cur.execute(
                "INSERT INTO products (brand_id, name, price, quantity) "
                "VALUES (%s, 'SAME', 1, 1)",
                (brand_id,),
            )
        db_connection.commit()


# ------------------------------------------------------------------ orders (P25)


def _make_product(admin_api, name, qty=5, lead_time_days=7):
    brand_id = admin_api.post("/api/brands", json={"name": f"OrderB{name}"}).json()["id"]
    response = admin_api.post(
        "/api/products",
        json={
            "brand_id": brand_id,
            "name": name,
            "price": 2.0,
            "quantity": qty,
            "lead_time_days": lead_time_days,
        },
    )
    assert response.status_code == 200
    return response.json()["id"]


def test_orders_require_auth(api):
    assert api.post("/api/orders", json={"product_id": 1, "qty": 1}).status_code == 401
    assert api.get("/api/orders").status_code == 401


def test_create_order_derives_expected_from_lead_time(api, admin_api):
    product_id = _make_product(admin_api, "LeadOrder", lead_time_days=12)

    response = admin_api.post("/api/orders", json={"product_id": product_id, "qty": 20})

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ordered"
    assert body["product_name"] == "LeadOrder"
    assert body["received_at"] is None
    from datetime import datetime

    created = datetime.fromisoformat(body["created_at"])
    expected = datetime.fromisoformat(body["expected_at"])
    assert 11 <= (expected - created).days <= 13  # lead_time_days = 12


def test_create_order_unknown_product_and_bad_qty(api, admin_api):
    assert (
        admin_api.post("/api/orders", json={"product_id": 999999, "qty": 5}).status_code
        == 404
    )
    assert (
        admin_api.post("/api/orders", json={"product_id": 1, "qty": 0}).status_code
        == 422
    )


def test_order_receive_adds_stock_and_records_movement(api, admin_api):
    product_id = _make_product(admin_api, "RecvOrder", qty=5)

    order_id = admin_api.post(
        "/api/orders", json={"product_id": product_id, "qty": 30}
    ).json()["id"]

    response = admin_api.post(f"/api/orders/{order_id}/receive")
    assert response.status_code == 200

    # Stock grew by the ordered quantity.
    listing = admin_api.get("/api/products", params={"search": "RecvOrder"})
    assert listing.json()["items"][0]["quantity"] == 35

    # A matching purchase_order movement was recorded.
    movements = admin_api.get("/api/movements", params={"limit": 15}).json()["items"]
    match = [
        m
        for m in movements
        if m["product_id"] == product_id
        and m["qty_delta"] == 30
        and m["reason"] == "purchase_order"
    ]
    assert len(match) == 1


def test_order_receive_twice_rejected(api, admin_api):
    product_id = _make_product(admin_api, "DoubleRecv")
    order_id = admin_api.post(
        "/api/orders", json={"product_id": product_id, "qty": 3}
    ).json()["id"]

    assert admin_api.post(f"/api/orders/{order_id}/receive").status_code == 200
    assert admin_api.post(f"/api/orders/{order_id}/receive").status_code == 400


def test_order_cancel_flow(api, admin_api):
    product_id = _make_product(admin_api, "CancelOrder")
    order_id = admin_api.post(
        "/api/orders", json={"product_id": product_id, "qty": 7}
    ).json()["id"]

    assert admin_api.post(f"/api/orders/{order_id}/cancel").status_code == 200
    # Cancelled orders cannot be received nor cancelled again.
    assert admin_api.post(f"/api/orders/{order_id}/receive").status_code == 400
    assert admin_api.post(f"/api/orders/{order_id}/cancel").status_code == 400


def test_orders_list_filters_and_paginates(api, admin_api):
    product_id = _make_product(admin_api, "ListOrder")
    ids = []
    for qty in (2, 4, 6):
        ids.append(
            admin_api.post("/api/orders", json={"product_id": product_id, "qty": qty}).json()["id"]
        )

    body = admin_api.get("/api/orders").json()
    assert body["total"] == 3
    assert all("product_name" in i and i["product_name"] == "ListOrder" for i in body["items"])

    # Receive one; the status filter narrows correctly.
    admin_api.post(f"/api/orders/{ids[2]}/receive")
    assert admin_api.get("/api/orders", params={"status": "received"}).json()["total"] == 1
    assert admin_api.get("/api/orders", params={"status": "ordered"}).json()["total"] == 2
    assert admin_api.get("/api/orders", params={"status": "bogus"}).status_code == 400

    # Pagination: one page of 2.
    page = admin_api.get("/api/orders", params={"limit": 2, "offset": 0}).json()
    assert len(page["items"]) == 2
    assert page["total"] == 3
