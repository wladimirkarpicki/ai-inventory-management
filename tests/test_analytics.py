"""
End-to-end tests for the P7 analytics endpoints: /api/movements,
/api/forecast and /api/recommendations (GET + limit/offset/total),
OpenRouter refinement behaviour, and the low_stock_alerts dashboard field.
"""

import json
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


def _insert_movements(db_conn, product_id, qty_per_day, days=5, reason="sale"):
    """Insert `days` daily movements of `qty_per_day` (negative = stock out)."""
    now = datetime.now()
    with db_conn.cursor() as cur:
        for i in range(1, days + 1):
            cur.execute(
                "INSERT INTO stock_movements (product_id, in_out, qty, reason, timestamp) "
                "VALUES (%s, %s, %s, %s, %s)",
                (
                    product_id,
                    "out" if qty_per_day < 0 else "in",
                    qty_per_day,
                    reason,
                    now - timedelta(days=i),
                ),
            )
    db_conn.commit()


# ------------------------------------------------------------------ /api/movements


def test_movements_requires_auth(api):
    assert api.get("/api/movements").status_code == 401


def test_movements_empty_when_none_exist(api, admin_api):
    response = admin_api.get("/api/movements")

    assert response.status_code == 200
    assert response.json() == {"items": [], "total": 0}


def test_movements_pagination_limit_offset(api, admin_api, db_connection):
    _brand_id, product_id = _insert_brand_product(db_connection, product_name="Paged", qty=10)
    _insert_movements(db_connection, product_id, qty_per_day=-1, days=25)

    first = admin_api.get("/api/movements", params={"limit": 10, "offset": 0})
    assert first.status_code == 200
    body = first.json()
    assert body["total"] == 25
    assert len(body["items"]) == 10
    # newest first
    timestamps = [item["timestamp"] for item in body["items"]]
    assert timestamps == sorted(timestamps, reverse=True)
    assert all(item["product_name"] == "Paged" for item in body["items"])
    assert all(item["in_out"] == "out" for item in body["items"])
    assert all(item["qty_delta"] == -1 for item in body["items"])

    second = admin_api.get("/api/movements", params={"limit": 10, "offset": 10})
    assert second.status_code == 200
    assert len(second.json()["items"]) == 10

    tail = admin_api.get("/api/movements", params={"limit": 10, "offset": 20})
    assert tail.status_code == 200
    assert len(tail.json()["items"]) == 5

    # pages are disjoint and cover all 25 movements
    ids1 = {item["movement_id"] for item in body["items"]}
    ids2 = {item["movement_id"] for item in second.json()["items"]}
    ids3 = {item["movement_id"] for item in tail.json()["items"]}
    assert len(ids1 | ids2 | ids3) == 25

    # limit above the max is rejected
    assert admin_api.get("/api/movements", params={"limit": 101}).status_code == 422


# ------------------------------------------------------------------ /api/forecast


def test_forecast_requires_auth(api):
    assert api.get("/api/forecast").status_code == 401


def test_forecast_structure_with_no_movements(api, admin_api, db_connection):
    _brand_id, product_id = _insert_brand_product(db_connection, product_name="NoMov", qty=10)

    response = admin_api.get("/api/forecast")

    assert response.status_code == 200
    body = response.json()
    assert body["total"] == 1
    forecasts = body["forecasts"]
    assert len(forecasts) == 1
    f = forecasts[0]
    assert f["product_id"] == product_id
    assert f["current_qty"] == 10
    assert set(f) == {
        "product_id", "name", "current_qty",
        "days_until_stockout", "recommended_restock_qty",
        "daily_consumption_rate", "daily_net_rate", "ai_refined",
    }
    # No movements → no trend: null days (the old 9999 sentinel is gone)
    assert f["daily_consumption_rate"] == 0.0
    assert f["days_until_stockout"] is None
    assert f["recommended_restock_qty"] == 0
    assert f["ai_refined"] is False


def test_forecast_linear_regression_on_movements(api, admin_api, db_connection):
    _brand_id, product_id = _insert_brand_product(db_connection, product_name="Reg", qty=10)
    _insert_movements(db_connection, product_id, qty_per_day=-2, days=5)

    response = admin_api.get("/api/forecast")

    assert response.status_code == 200
    f = {row["product_id"]: row for row in response.json()["forecasts"]}[product_id]
    assert f["daily_consumption_rate"] == 2.0
    assert f["days_until_stockout"] == 5  # 10 units / 2 per day
    # restock covers the per-product lead time (default 7) + 10% safety:
    # 2 * 7 * 1.1 = 15.4 → target max(10 + 15.4, reorder_point 10) → round(25.4 - 10) = 15
    assert f["recommended_restock_qty"] == 15
    assert f["ai_refined"] is False  # conftest disables OpenRouter


def test_forecast_stable_stock_has_no_stockout(api, admin_api, db_connection):
    _brand_id, product_id = _insert_brand_product(db_connection, product_name="Stable", qty=10)
    _insert_movements(db_connection, product_id, qty_per_day=5, days=5, reason="restock")

    response = admin_api.get("/api/forecast")

    assert response.status_code == 200
    f = {row["product_id"]: row for row in response.json()["forecasts"]}[product_id]
    assert f["daily_consumption_rate"] == 0.0
    assert f["days_until_stockout"] is None  # growing stock, no depletion


def test_forecast_sorted_and_paginated(api, admin_api, db_connection):
    # Fast depletes in ~5 days, Slow in ~10 days, Idle has no consumption.
    _b, pid_fast = _insert_brand_product(db_connection, brand_name="FastCo", product_name="Fast", qty=10)
    _b, pid_slow = _insert_brand_product(db_connection, brand_name="SlowCo", product_name="Slow", qty=10)
    _b, pid_idle = _insert_brand_product(db_connection, brand_name="IdleCo", product_name="Idle", qty=42)
    _insert_movements(db_connection, pid_fast, qty_per_day=-2, days=5)
    _insert_movements(db_connection, pid_slow, qty_per_day=-1, days=5)

    response = admin_api.get("/api/forecast", params={"limit": 2, "offset": 0})
    assert response.status_code == 200
    body = response.json()
    assert body["total"] == 3
    # most urgent first, no-consumption items last
    assert [f["product_id"] for f in body["forecasts"]] == [pid_fast, pid_slow]

    tail = admin_api.get("/api/forecast", params={"limit": 2, "offset": 2})
    assert tail.status_code == 200
    tail_body = tail.json()
    assert tail_body["total"] == 3
    assert [f["product_id"] for f in tail_body["forecasts"]] == [pid_idle]
    assert tail_body["forecasts"][0]["days_until_stockout"] is None


# ------------------------------------------------------------------ OpenRouter refinement


class _FakeOpenRouterResponse:
    def __init__(self, payload: dict):
        self._payload = payload

    def read(self) -> bytes:
        return json.dumps(self._payload).encode()

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False


def test_openrouter_skips_without_key(api, admin_api, db_connection, capsys):
    # conftest autouse fixture sets an empty OPENROUTER_API_KEY
    _brand_id, product_id = _insert_brand_product(db_connection, product_name="NoKey", qty=10)
    _insert_movements(db_connection, product_id, qty_per_day=-1, days=5)

    response = admin_api.get("/api/forecast")

    assert response.status_code == 200
    f = response.json()["forecasts"][0]
    assert f["ai_refined"] is False
    assert "openrouter: skip, OPENROUTER_API_KEY not set" in capsys.readouterr().out


def test_openrouter_success_refines_by_product_id(api, admin_api, db_connection, monkeypatch, capsys):
    monkeypatch.setenv("OPENROUTER_API_KEY", "test-key")
    monkeypatch.setenv("OPENROUTER_MODEL", "test-model")
    _b, pid_a = _insert_brand_product(db_connection, brand_name="RefACo", product_name="RefA", qty=10)
    _b, pid_b = _insert_brand_product(db_connection, brand_name="RefBCo", product_name="RefB", qty=10)
    _insert_movements(db_connection, pid_a, qty_per_day=-2, days=5)
    _insert_movements(db_connection, pid_b, qty_per_day=-1, days=5)

    def fake_urlopen(req, timeout=None):
        # Deliberately shuffled: refinement must map by product_id, not by index.
        content = json.dumps([
            {"product_id": pid_b, "days_until_stockout": 3, "recommended_restock_qty": 99},
            {"product_id": pid_a, "days_until_stockout": 7, "recommended_restock_qty": 55},
        ])
        return _FakeOpenRouterResponse({"choices": [{"message": {"content": content}}]})

    monkeypatch.setattr(main_module.urllib.request, "urlopen", fake_urlopen)

    response = admin_api.get("/api/forecast")

    assert response.status_code == 200
    by_pid = {f["product_id"]: f for f in response.json()["forecasts"]}
    assert by_pid[pid_a]["days_until_stockout"] == 7
    assert by_pid[pid_a]["recommended_restock_qty"] == 55
    assert by_pid[pid_a]["ai_refined"] is True
    assert by_pid[pid_b]["days_until_stockout"] == 3
    assert by_pid[pid_b]["recommended_restock_qty"] == 99
    assert by_pid[pid_b]["ai_refined"] is True
    out = capsys.readouterr().out
    assert "openrouter: refining 2 items (model=test-model)" in out
    assert "openrouter: ok, refined 2" in out


def test_openrouter_failure_falls_back_to_regression(api, admin_api, db_connection, monkeypatch, capsys):
    monkeypatch.setenv("OPENROUTER_API_KEY", "test-key")

    def fake_urlopen(req, timeout=None):
        raise RuntimeError("boom")

    monkeypatch.setattr(main_module.urllib.request, "urlopen", fake_urlopen)
    _brand_id, product_id = _insert_brand_product(db_connection, product_name="Fallback", qty=10)
    _insert_movements(db_connection, product_id, qty_per_day=-2, days=5)

    response = admin_api.get("/api/forecast")

    assert response.status_code == 200
    f = response.json()["forecasts"][0]
    assert f["ai_refined"] is False
    assert f["days_until_stockout"] == 5  # regression value untouched
    assert f["recommended_restock_qty"] == 15
    assert "openrouter: failed: boom — regression fallback" in capsys.readouterr().out


def test_openrouter_success_with_markdown_fence(api, admin_api, db_connection, monkeypatch, capsys):
    # free-pool reasoning models may wrap the JSON in a ```json fence
    monkeypatch.setenv("OPENROUTER_API_KEY", "test-key")
    _brand_id, product_id = _insert_brand_product(db_connection, product_name="Fenced", qty=10)
    _insert_movements(db_connection, product_id, qty_per_day=-2, days=5)

    def fake_urlopen(req, timeout=None):
        content = (
            "```json\n"
            + json.dumps([
                {"product_id": product_id, "days_until_stockout": 4, "recommended_restock_qty": 12},
            ])
            + "\n```"
        )
        return _FakeOpenRouterResponse({"choices": [{"message": {"content": content}}]})

    monkeypatch.setattr(main_module.urllib.request, "urlopen", fake_urlopen)

    response = admin_api.get("/api/forecast")

    assert response.status_code == 200
    f = response.json()["forecasts"][0]
    assert f["ai_refined"] is True
    assert f["days_until_stockout"] == 4
    assert "openrouter: ok, refined 1" in capsys.readouterr().out


def test_openrouter_success_with_prose_preamble(api, admin_api, db_connection, monkeypatch, capsys):
    # ...or prepend CoT prose before the JSON array
    monkeypatch.setenv("OPENROUTER_API_KEY", "test-key")
    _brand_id, product_id = _insert_brand_product(db_connection, product_name="Chatty", qty=10)
    _insert_movements(db_connection, product_id, qty_per_day=-2, days=5)

    def fake_urlopen(req, timeout=None):
        payload = json.dumps([
            {"product_id": product_id, "days_until_stockout": 6, "recommended_restock_qty": 21},
        ])
        content = f"Sure! Reviewing the trends first.\nHere is the refined array: {payload}"
        return _FakeOpenRouterResponse({"choices": [{"message": {"content": content}}]})

    monkeypatch.setattr(main_module.urllib.request, "urlopen", fake_urlopen)

    response = admin_api.get("/api/forecast")

    assert response.status_code == 200
    f = response.json()["forecasts"][0]
    assert f["ai_refined"] is True
    assert f["days_until_stockout"] == 6
    assert "openrouter: ok, refined 1" in capsys.readouterr().out


def test_openrouter_garbage_content_falls_back(api, admin_api, db_connection, monkeypatch, capsys):
    monkeypatch.setenv("OPENROUTER_API_KEY", "test-key")
    _brand_id, product_id = _insert_brand_product(db_connection, product_name="Garbage", qty=10)
    _insert_movements(db_connection, product_id, qty_per_day=-2, days=5)

    def fake_urlopen(req, timeout=None):
        return _FakeOpenRouterResponse({"choices": [{"message": {"content": "no json here"}}]})

    monkeypatch.setattr(main_module.urllib.request, "urlopen", fake_urlopen)

    response = admin_api.get("/api/forecast")

    assert response.status_code == 200
    f = response.json()["forecasts"][0]
    assert f["ai_refined"] is False
    assert f["days_until_stockout"] == 5  # regression value kept
    assert (
        "openrouter: failed: response was not a JSON array — regression fallback"
        in capsys.readouterr().out
    )


# ------------------------------------------------------------------ /api/recommendations


def test_recommendations_requires_auth(api):
    assert api.get("/api/recommendations").status_code == 401


def test_recommendations_lists_low_stock(api, admin_api, db_connection):
    _brand_id, product_id = _insert_brand_product(
        db_connection, brand_name="LowCo", product_name="LowStock", qty=3
    )
    _insert_movements(db_connection, product_id, qty_per_day=-2, days=5)
    _insert_brand_product(db_connection, brand_name="HealthyCo", product_name="Healthy", qty=100)

    response = admin_api.get("/api/recommendations")

    assert response.status_code == 200
    body = response.json()
    assert body["total"] == 1
    items = body["recommendations"]
    assert len(items) == 1
    assert items[0]["name"] == "LowStock"
    assert items[0]["current_qty"] == 3
    assert items[0]["recommended_qty"] > 0
    assert all(item["name"] != "Healthy" for item in items)


def test_recommendations_empty_when_all_healthy(api, admin_api, db_connection):
    _insert_brand_product(db_connection, brand_name="OnlyHealthy", product_name="Healthy", qty=100)

    response = admin_api.get("/api/recommendations")

    assert response.status_code == 200
    assert response.json() == {"recommendations": [], "total": 0}


def test_recommendations_sorted_by_urgency(api, admin_api, db_connection):
    # Fast depletes in ~5 days (< lead_time_days=7) → recommended;
    # Slow depletes in ~10 days (not < 7, qty=10 not < 10) → excluded;
    # LowNoTrend qty=2 (< reorder_point=10) → recommended.
    _b, pid_fast = _insert_brand_product(db_connection, brand_name="RecFast", product_name="Fast", qty=10)
    _b, pid_slow = _insert_brand_product(db_connection, brand_name="RecSlow", product_name="Slow", qty=10)
    _b, pid_low = _insert_brand_product(db_connection, brand_name="RecLow", product_name="LowNoTrend", qty=2)
    _insert_movements(db_connection, pid_fast, qty_per_day=-2, days=5)
    _insert_movements(db_connection, pid_slow, qty_per_day=-1, days=5)

    response = admin_api.get("/api/recommendations", params={"limit": 2, "offset": 0})

    assert response.status_code == 200
    body = response.json()
    # Only Fast (days<7) + LowNoTrend (qty<10) = 2 items, sorted by urgency (days ASC, unknown last)
    assert body["total"] == 2
    assert [i["product_id"] for i in body["recommendations"]] == [pid_fast, pid_low]

    tail = admin_api.get("/api/recommendations", params={"limit": 2, "offset": 2})
    assert tail.status_code == 200
    tail_items = tail.json()["recommendations"]
    assert tail_items == []


# ------------------------------------------------------------------ dashboard stats


def test_dashboard_stats_has_low_stock_alerts(api, admin_api, db_connection):
    _brand_id, product_id = _insert_brand_product(
        db_connection, brand_name="TestAlert", product_name="LowStock", qty=2
    )
    _insert_brand_product(db_connection, brand_name="TestHealthyAlert", product_name="Healthy", qty=50)

    response = admin_api.get("/api/dashboard/stats")

    assert response.status_code == 200
    stats = response.json()
    assert stats["low_stock"] == 1
    assert "low_stock_alerts" in stats
    alerts = stats["low_stock_alerts"]
    assert len(alerts) == 1
    assert alerts[0]["product_id"] == product_id
    assert alerts[0]["name"] == "LowStock"
    assert alerts[0]["remaining_qty"] == 2
    assert stats["low_stock_threshold"] == 5


def test_dashboard_stats_low_stock_alerts_capped_at_top10(api, admin_api, db_connection):
    # 12 products below the threshold: the alert list is capped at 10,
    # while the low_stock counter keeps the full count.
    quantities = [4, 3, 2, 1, 0, 4, 3, 2, 1, 0, 3, 2]
    for idx, qty in enumerate(quantities):
        _insert_brand_product(
            db_connection,
            brand_name=f"CapBrand{idx}",
            product_name=f"CappedProduct{idx:02d}",
            qty=qty,
        )

    response = admin_api.get("/api/dashboard/stats")

    assert response.status_code == 200
    stats = response.json()
    assert stats["low_stock"] == 12
    alerts = stats["low_stock_alerts"]
    assert len(alerts) == 10
    # top-10 by remaining_qty ascending: least stock left first
    remaining = [a["remaining_qty"] for a in alerts]
    assert remaining == sorted(remaining)
    assert remaining[0] == 0
