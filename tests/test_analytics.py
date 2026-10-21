"""
End-to-end tests for the P6 analytics endpoints: /api/movements,
/api/forecast, /api/recommendations and the low_stock_alerts dashboard field.
"""

import uuid
from datetime import datetime, timedelta

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


def _insert_brand_product(db_conn, brand_name="Acme", product_name="Widget", qty=10, price=9.99):
    """Insert a brand + product and return (brand_id, product_id)."""
    with db_conn.cursor() as cur:
        cur.execute("INSERT INTO brands (name) VALUES (%s) RETURNING id", (brand_name,))
        brand_id = cur.fetchone()[0]
        cur.execute(
            "INSERT INTO products (brand_id, name, price, quantity) VALUES (%s, %s, %s, %s) RETURNING id",
            (brand_id, product_name, price, qty),
        )
        product_id = cur.fetchone()[0]
    db_conn.commit()
    return brand_id, product_id


def _clear_all(db_conn):
    """Truncate all relevant tables (called after each test via conftest, but be defensive)."""
    with db_conn.cursor() as cur:
        cur.execute("TRUNCATE users, products, brands, stock_movements RESTART IDENTITY CASCADE")
    db_conn.commit()


# ------------------------------------------------------------------ /api/movements


def test_movements_requires_auth(api):
    assert api.post("/api/movements").status_code == 401


def test_movements_empty_when_none_exist(api, admin_api):
    response = admin_api.post("/api/movements")

    assert response.status_code == 200
    assert response.json() == []


def test_movements_returns_last_20_descending(api, admin_api, db_connection):
    # Insert brand + product + 25 movements
    with db_connection.cursor() as cur:
        uid = str(uuid.uuid4())[:4]
        cur.execute("INSERT INTO brands (name) VALUES (%s) RETURNING id", (f"TestMov_{uid}",))
        brand_id = cur.fetchone()[0]
        cur.execute(
            "INSERT INTO products (brand_id, name, price, quantity) VALUES (%s, %s, %s, %s) RETURNING id",
            (brand_id, f"Product_{uid}", 9.99, 10),
        )
        product_id = cur.fetchone()[0]
    db_connection.commit()

    now = datetime.now()
    with db_connection.cursor() as cur:
        for i in range(25):
            cur.execute(
                "INSERT INTO stock_movements (product_id, in_out, qty, reason, timestamp) "
                "VALUES (%s, %s, %s, %s, %s)",
                (product_id, "out", -1, "sale", now - timedelta(days=25 - i)),
            )
    db_connection.commit()

    response = admin_api.post("/api/movements")

    assert response.status_code == 200
    items = response.json()
    assert len(items) == 20  # capped at 20
    # newest first: timestamps should be non-increasing
    timestamps = [item["timestamp"] for item in items]
    assert timestamps == sorted(timestamps, reverse=True)
    assert all(item["product_name"] == f"Product_{uid}" for item in items)
    assert all(item["in_out"] == "out" for item in items)
    assert all(item["qty_delta"] == -1 for item in items)


# ------------------------------------------------------------------ /api/forecast


def test_forecast_requires_auth(api):
    assert api.post("/api/forecast").status_code == 401


def test_forecast_structure_with_no_movements(api, admin_api, db_connection):
    # Insert brand + product with no movements
    with db_connection.cursor() as cur:
        uid = str(uuid.uuid4())[:4]
        cur.execute("INSERT INTO brands (name) VALUES (%s) RETURNING id", (f"TestNoMov_{uid}",))
        brand_id = cur.fetchone()[0]
        cur.execute(
            "INSERT INTO products (brand_id, name, price, quantity) VALUES (%s, %s, %s, %s) RETURNING id",
            (brand_id, f"Product_{uid}", 9.99, 10),
        )
        product_id = cur.fetchone()[0]
    db_connection.commit()

    response = admin_api.post("/api/forecast")

    assert response.status_code == 200
    forecasts = response.json()["forecasts"]
    assert len(forecasts) == 1
    f = forecasts[0]
    assert f["product_id"] == product_id
    assert f["name"] == f"Product_{uid}"
    assert f["current_qty"] == 10
    assert set(f) == {
        "product_id", "name", "current_qty",
        "days_until_stockout", "recommended_restock_qty",
        "daily_consumption_rate", "daily_net_rate", "ai_refined",
    }
    # No movements → no consumption trend; all zeros/sentinel
    assert f["daily_consumption_rate"] == 0.0
    assert f["days_until_stockout"] == 9999  # sentinel
    assert f["recommended_restock_qty"] == 0
    assert f["ai_refined"] is False


def test_forecast_linear_regression_on_movements(api, admin_api, db_connection):
    # Product starts at qty=10; 5 days of -2/day net outflow
    with db_connection.cursor() as cur:
        uid = str(uuid.uuid4())[:4]
        cur.execute("INSERT INTO brands (name) VALUES (%s) RETURNING id", (f"TestReg_{uid}",))
        brand_id = cur.fetchone()[0]
        cur.execute(
            "INSERT INTO products (brand_id, name, price, quantity) VALUES (%s, %s, %s, %s) RETURNING id",
            (brand_id, f"Product_{uid}", 9.99, 10),
        )
        product_id = cur.fetchone()[0]
        # Insert 5 movements: qty=-2 per day for 5 days
        now = datetime.now()
        for i in range(1, 6):
            cur.execute(
                "INSERT INTO stock_movements (product_id, in_out, qty, reason, timestamp) "
                "VALUES (%s, %s, %s, %s, %s)",
                (product_id, "out", -2, "sale", now - timedelta(days=i)),
            )
    db_connection.commit()

    response = admin_api.post("/api/forecast")

    assert response.status_code == 200
    forecasts = {row["product_id"]: row for row in response.json()["forecasts"]}
    f = forecasts[product_id]
    assert f["name"] == f"Product_{uid}"
    assert f["current_qty"] == 10
    # slope = -2 / day → consumption rate 2.0
    assert f["daily_consumption_rate"] == 2.0
    # 10 units / 2 per day = 5 days
    assert f["days_until_stockout"] == 5
    # recommended_restock_qty covers 14-day lead + 10% safety
    # needed = 2 * 14 * 1.1 = 30.8 → target = max(10 + 30.8, 5) = 40.8 → round(40.8 - 10) = 31
    assert f["recommended_restock_qty"] == 31
    assert f["ai_refined"] is False  # OpenRouter disabled in tests


def test_forecast_stable_stock_has_no_restock(api, admin_api, db_connection):
    # Product with inflow: +5/day → stock growing, no depletion
    with db_connection.cursor() as cur:
        uid = str(uuid.uuid4())[:4]
        cur.execute("INSERT INTO brands (name) VALUES (%s) RETURNING id", (f"TestStable_{uid}",))
        brand_id = cur.fetchone()[0]
        cur.execute(
            "INSERT INTO products (brand_id, name, price, quantity) VALUES (%s, %s, %s, %s) RETURNING id",
            (brand_id, f"Product_{uid}", 9.99, 10),
        )
        product_id = cur.fetchone()[0]
        # Insert 5 movements: qty=+5 per day for 5 days (inflow)
        now = datetime.now()
        for i in range(1, 6):
            cur.execute(
                "INSERT INTO stock_movements (product_id, in_out, qty, reason, timestamp) "
                "VALUES (%s, %s, %s, %s, %s)",
                (product_id, "in", 5, "restock", now - timedelta(days=i)),
            )
    db_connection.commit()

    response = admin_api.post("/api/forecast")

    assert response.status_code == 200
    forecasts = {row["product_id"]: row for row in response.json()["forecasts"]}
    f = forecasts[product_id]
    assert f["daily_consumption_rate"] == 0.0
    # Inflow → growing stock, no stockout risk
    assert f["days_until_stockout"] == 9999  # sentinel: no depletion


# ------------------------------------------------------------------ /api/recommendations


def test_recommendations_requires_auth(api):
    assert api.post("/api/recommendations").status_code == 401


def test_recommendations_lists_low_stock(api, admin_api, db_connection):
    # Low-stock product (qty below threshold of 5) with depletion trend
    with db_connection.cursor() as cur:
        uid = str(uuid.uuid4())[:4]
        cur.execute("INSERT INTO brands (name) VALUES (%s) RETURNING id", (f"TestLow_{uid}",))
        brand_id = cur.fetchone()[0]
        cur.execute(
            "INSERT INTO products (brand_id, name, price, quantity) VALUES (%s, %s, %s, %s) RETURNING id",
            (brand_id, f"LowStock_{uid}", 9.99, 3),  # qty=3 < threshold=5
        )
        product_id = cur.fetchone()[0]
        # Insert 5 movements: qty=-2 per day for 5 days (depleting fast)
        now = datetime.now()
        for i in range(1, 6):
            cur.execute(
                "INSERT INTO stock_movements (product_id, in_out, qty, reason, timestamp) "
                "VALUES (%s, %s, %s, %s, %s)",
                (product_id, "out", -2, "sale", now - timedelta(days=i)),
            )
    db_connection.commit()

    # Also insert a healthy product (large qty, no depletion)
    with db_connection.cursor() as cur:
        uid2 = str(uuid.uuid4())[:4]
        cur.execute("INSERT INTO brands (name) VALUES (%s) RETURNING id", (f"TestHealthy_{uid2}",))
        brand_id2 = cur.fetchone()[0]
        cur.execute(
            "INSERT INTO products (brand_id, name, price, quantity) VALUES (%s, %s, %s, %s) RETURNING id",
            (brand_id2, f"Healthy_{uid2}", 9.99, 100),  # qty=100 >> threshold
        )
        # No movements for healthy product
    db_connection.commit()

    response = admin_api.post("/api/recommendations")

    assert response.status_code == 200
    items = response.json()["recommendations"]
    low_items = [item for item in items if item["product_id"] is not None and f"LowStock_{uid}" in item.get("name", "")]
    assert len(low_items) == 1
    assert low_items[0]["name"] == f"LowStock_{uid}"
    assert low_items[0]["current_qty"] == 3
    assert low_items[0]["recommended_qty"] > 0
    # Healthy product should NOT be in recommendations
    healthy_names = [item["name"] for item in items]
    assert f"Healthy_{uid2}" not in healthy_names


def test_recommendations_empty_when_all_healthy(api, admin_api, db_connection):
    with db_connection.cursor() as cur:
        uid = str(uuid.uuid4())[:4]
        cur.execute("INSERT INTO brands (name) VALUES (%s) RETURNING id", (f"TestHealthyOnly_{uid}",))
        brand_id = cur.fetchone()[0]
        cur.execute(
            "INSERT INTO products (brand_id, name, price, quantity) VALUES (%s, %s, %s, %s) RETURNING id",
            (brand_id, f"Healthy_{uid}", 9.99, 100),  # qty=100 >> threshold, no movements
        )
    db_connection.commit()

    response = admin_api.post("/api/recommendations")

    assert response.status_code == 200
    assert response.json()["recommendations"] == []


# ------------------------------------------------------------------ dashboard stats


def test_dashboard_stats_has_low_stock_alerts(api, admin_api, db_connection):
    with db_connection.cursor() as cur:
        uid = str(uuid.uuid4())[:4]
        cur.execute("INSERT INTO brands (name) VALUES (%s) RETURNING id", (f"TestAlert_{uid}",))
        brand_id = cur.fetchone()[0]
        cur.execute(
            "INSERT INTO products (brand_id, name, price, quantity) VALUES (%s, %s, %s, %s) RETURNING id",
            (brand_id, f"LowStock_{uid}", 9.99, 2),  # qty=2 < threshold=5
        )
        uid2 = str(uuid.uuid4())[:4]
        cur.execute("INSERT INTO brands (name) VALUES (%s) RETURNING id", (f"TestHealthyAlert_{uid2}",))
        brand_id2 = cur.fetchone()[0]
        cur.execute(
            "INSERT INTO products (brand_id, name, price, quantity) VALUES (%s, %s, %s, %s) RETURNING id",
            (brand_id2, f"Healthy_{uid2}", 9.99, 50),  # qty=50 >> threshold
        )
    db_connection.commit()

    response = admin_api.get("/api/dashboard/stats")

    assert response.status_code == 200
    stats = response.json()
    assert stats["low_stock"] == 1
    assert "low_stock_alerts" in stats
    alerts = stats["low_stock_alerts"]
    assert len(alerts) == 1
    assert alerts[0]["product_id"] is not None
    assert alerts[0]["name"] == f"LowStock_{uid}"
    assert alerts[0]["remaining_qty"] == 2
    assert stats["low_stock_threshold"] == 5
