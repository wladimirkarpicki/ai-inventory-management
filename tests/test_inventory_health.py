"""
Tests for the Inventory Health & Replenishment feature: the per-product
`min_quantity` column and its DB default/CHECK, the new `min_quantity`
field on the products endpoints, the dedicated PATCH .../min-quantity
endpoint, the GET /api/inventory-health report (summary + severity
ordering + status filter), and its CSV export.

The stock-status classes bridge to the existing reorder-point quick
filter; one test pins that the two concepts stay independent.
"""

import csv

import pytest
from conftest import (
    ADMIN_PASSWORD,
    ADMIN_USERNAME,
    REGULAR_PASSWORD,
    REGULAR_USERNAME,
    REPO_ROOT,
)
from fastapi.testclient import TestClient

import main as main_module


@pytest.fixture()
def api():
    return TestClient(main_module.app)


def _bearer(token):
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture()
def admin_api(api):
    """A client authorized as the first account, which is an admin."""
    response = api.post(
        "/api/auth/setup",
        json={"username": ADMIN_USERNAME, "password": ADMIN_PASSWORD},
    )
    assert response.status_code == 200
    api.headers.update(_bearer(response.json()["access_token"]))
    return api


@pytest.fixture()
def user_api(api, admin_api):
    """A second client authorized as a regular user created by the admin."""
    response = admin_api.post(
        "/api/users",
        json={
            "username": REGULAR_USERNAME,
            "password": REGULAR_PASSWORD,
            "role": "user",
        },
    )
    assert response.status_code == 200
    regular_client = TestClient(main_module.app)
    login_resp = regular_client.post(
        "/api/auth/login",
        json={"username": REGULAR_USERNAME, "password": REGULAR_PASSWORD},
    )
    regular_client.headers.update(_bearer(login_resp.json()["access_token"]))
    return regular_client


def _make_brand(client, name="HealthCo"):
    response = client.post("/api/brands", json={"name": name})
    assert response.status_code == 200
    return response.json()["id"]


def _make_product(
    client,
    brand_id,
    name,
    quantity,
    min_quantity=None,
    reorder_point=10,
    price=1.0,
):
    payload = {
        "brand_id": brand_id,
        "name": name,
        "price": price,
        "quantity": quantity,
        "reorder_point": reorder_point,
    }
    # min_quantity omitted on purpose in several tests to exercise the
    # schema default; only send it when the case asks for an explicit value.
    if min_quantity is not None:
        payload["min_quantity"] = min_quantity
    response = client.post("/api/products", json=payload)
    assert response.status_code == 200
    return response.json()


def _seed_health_dataset(admin_api):
    """
    One brand holding products in every class, inserted so creation order
    differs from the report order — proving the report really sorts.
    Returns a mapping of label -> product id.
    """
    brand_id = _make_brand(admin_api, name="SeverityCo")
    ids = {}
    ids["healthy"] = _make_product(
        admin_api, brand_id, "HealthyBaseline", quantity=5, min_quantity=5
    )["id"]
    ids["overstocked"] = _make_product(
        admin_api, brand_id, "Overstocked", quantity=100, min_quantity=5
    )["id"]
    ids["low_small"] = _make_product(
        admin_api, brand_id, "LowSmallShortage", quantity=8, min_quantity=12
    )["id"]
    ids["low_big"] = _make_product(
        admin_api, brand_id, "LowBigShortage", quantity=2, min_quantity=10
    )["id"]
    ids["out5"] = _make_product(admin_api, brand_id, "OutMin5", quantity=0, min_quantity=5)["id"]
    ids["out10"] = _make_product(admin_api, brand_id, "OutMin10", quantity=0, min_quantity=10)["id"]
    return ids


# ------------------------------------------------------------------ pure helpers


@pytest.mark.parametrize(
    "quantity,min_quantity,expected",
    [
        (0, 5, "OUT OF STOCK"),
        (1, 5, "LOW STOCK"),
        (4, 5, "LOW STOCK"),
        (5, 5, "IN STOCK"),
        (6, 5, "IN STOCK"),
        (100, 5, "IN STOCK"),
        (None, 5, "OUT OF STOCK"),  # NULL on-hand is treated as 0, not a crash
        (0, 0, "OUT OF STOCK"),
        (1, 0, "IN STOCK"),  # min 0 -> "low" is impossible, everything on hand is IN STOCK
        (5, 0, "IN STOCK"),
        (None, 0, "OUT OF STOCK"),
    ],
)
def test_stock_status_classifies_boundaries(quantity, min_quantity, expected):
    assert main_module.stock_status(quantity, min_quantity) == expected


@pytest.mark.parametrize(
    "quantity,min_quantity,expected",
    [
        (0, 5, 5),
        (1, 5, 4),
        (4, 5, 1),
        (5, 5, 0),
        (6, 5, 0),
        (100, 5, 0),
        (None, 5, 5),  # unknown stock -> order the full minimum
        (0, 0, 0),
        (5, 0, 0),
    ],
)
def test_recommended_to_order_covers_shortfall(quantity, min_quantity, expected):
    assert main_module.recommended_to_order(quantity, min_quantity) == expected


def test_health_sort_key_orders_by_severity_shortage_then_id():
    def row(product_id, status, current, minimum):
        return {
            "product_id": product_id,
            "stock_status": status,
            "current_quantity": current,
            "min_quantity": minimum,
        }

    rows = [
        row(5, "LOW STOCK", 2, 10),  # shortage 8
        row(1, "IN STOCK", 20, 5),  # surplus 15
        row(7, "OUT OF STOCK", 0, 20),  # shortage 20 (biggest)
        row(2, "OUT OF STOCK", 0, 5),  # shortage 5, lower id
        row(10, "OUT OF STOCK", 0, 5),  # shortage 5, higher id
        row(3, "LOW STOCK", 8, 10),  # shortage 2
    ]

    ordered = sorted(rows, key=main_module._health_sort_key)

    # Severity first; within OUT OF STOCK largest shortage (20) before the
    # two tied at 5, and that tie broken by ascending product id (2 < 10).
    assert [r["product_id"] for r in ordered] == [7, 2, 10, 5, 3, 1]


def test_health_sort_key_puts_the_least_overstocked_in_stock_first():
    """
    Inside the healthy class the same rule reads most usefully: the product
    sitting closest to its minimum (the next one to fall below it) leads,
    and the deeply overstocked one trails. The spec only constrains LOW
    STOCK, so this pins the intent rather than a stated requirement.
    """

    def row(product_id, current, minimum):
        return {
            "product_id": product_id,
            "stock_status": "IN STOCK",
            "current_quantity": current,
            "min_quantity": minimum,
        }

    rows = [
        row(2, 100, 5),  # surplus 95
        row(1, 5, 5),  # exactly at the minimum, deficit 0
        row(3, 6, 5),  # surplus 1
    ]

    ordered = sorted(rows, key=main_module._health_sort_key)

    assert [r["product_id"] for r in ordered] == [1, 3, 2]


# ------------------------------------------------------------------ DB migration


def test_min_quantity_column_defaults_to_five_without_explicit_value(db_connection):
    with db_connection.cursor() as cur:
        cur.execute("INSERT INTO brands (name) VALUES ('DefaultCo') RETURNING id")
        brand_id = cur.fetchone()[0]
        # Omit min_quantity entirely; the schema DEFAULT must supply 5.
        cur.execute(
            "INSERT INTO products (brand_id, name, price, quantity) "
            "VALUES (%s, %s, %s, %s) RETURNING id, min_quantity",
            (brand_id, "Implicit", 1.0, 3),
        )
        row = cur.fetchone()
    db_connection.commit()

    assert row is not None
    assert row[1] == 5


def test_min_quantity_check_constraint_rejects_negative(db_connection):
    import psycopg.errors

    with db_connection.cursor() as cur:
        cur.execute("INSERT INTO brands (name) VALUES ('NegCo') RETURNING id")
        brand_id = cur.fetchone()[0]
    db_connection.commit()

    # The CHECK (min_quantity >= 0) guards the column even if the API layer
    # were bypassed, so a direct negative INSERT must fail at the database.
    with pytest.raises(psycopg.errors.CheckViolation):
        with db_connection.cursor() as cur:
            cur.execute(
                "INSERT INTO products (brand_id, name, price, quantity, min_quantity) "
                "VALUES (%s, %s, %s, %s, %s)",
                (brand_id, "Broken", 1.0, 1, -1),
            )
        db_connection.commit()


def test_migration_005_backfills_existing_rows_with_the_default(db_connection):
    """
    Requirement: existing products receive the default value.

    Runs the real migration file against a table missing the column, with a
    product row already present, and asserts that row ends up at 5. The
    whole effect is wrapped in one transaction and rolled back, so the
    column is intact for the tests that follow.
    """

    migration = (REPO_ROOT / "migrations" / "005_min_quantity.sql").read_text(encoding="utf-8")

    # Open a transaction on the shared connection: PostgreSQL DDL is
    # transactional, so the schema changes below are undone by the rollback.
    db_connection.rollback()

    try:
        with db_connection.cursor() as cur:
            # Step back to the pre-migration schema.
            cur.execute("ALTER TABLE products DROP COLUMN min_quantity")

            # A product row from before the feature existed.
            cur.execute("INSERT INTO brands (name) VALUES ('LegacyCo') RETURNING id")
            brand_id = cur.fetchone()[0]
            cur.execute(
                "INSERT INTO products (brand_id, name, price, quantity) VALUES (%s, %s, %s, %s)",
                (brand_id, "LegacyWidget", 9.99, 2),
            )

            # Apply the shipped migration.
            cur.execute(migration)

            cur.execute("SELECT min_quantity FROM products WHERE name = %s", ("LegacyWidget",))
            backfilled = cur.fetchone()

        assert backfilled is not None
        assert backfilled[0] == 5
    finally:
        db_connection.rollback()

    # Sanity: the rollback really restored the column for later tests.
    with db_connection.cursor() as cur:
        cur.execute("SELECT min_quantity FROM products LIMIT 1")
    db_connection.commit()


# ------------------------------------------------------------------ POST /api/products


def test_create_product_without_min_quantity_defaults_to_five(admin_api):
    brand_id = _make_brand(admin_api, name="DefCreateCo")
    payload = _make_product(admin_api, brand_id, "NoMin", quantity=5)

    assert payload["min_quantity"] == 5


def test_create_product_echoes_explicit_min_quantity(admin_api, db_connection):
    brand_id = _make_brand(admin_api, name="EchoCo")
    payload = _make_product(admin_api, brand_id, "WithMin", quantity=5, min_quantity=25)

    assert payload["min_quantity"] == 25

    # The value is persisted to the column, not just echoed back.
    with db_connection.cursor() as cur:
        cur.execute("SELECT min_quantity FROM products WHERE id = %s", (payload["id"],))
        (stored,) = cur.fetchone()
    db_connection.commit()
    assert stored == 25


def test_create_product_rejects_negative_min_quantity(admin_api):
    brand_id = _make_brand(admin_api, name="NegCreateCo")
    response = admin_api.post(
        "/api/products",
        json={"brand_id": brand_id, "name": "Bad", "price": 1.0, "quantity": 1, "min_quantity": -1},
    )

    assert response.status_code == 422


# ------------------------------------------------------------------ PATCH /min-quantity


def test_patch_min_quantity_updates_value_and_reports_status(admin_api, db_connection):
    brand_id = _make_brand(admin_api, name="PatchCo")
    product_id = _make_product(admin_api, brand_id, "Widget", quantity=3, min_quantity=5)["id"]

    response = admin_api.patch(f"/api/products/{product_id}/min-quantity", json={"min_quantity": 2})
    assert response.status_code == 200
    body = response.json()
    assert body["id"] == product_id
    assert body["min_quantity"] == 2
    # With 3 on hand against a min of 2 the product is no longer low.
    assert body["stock_status"] == "IN STOCK"

    with db_connection.cursor() as cur:
        cur.execute("SELECT min_quantity FROM products WHERE id = %s", (product_id,))
        (stored,) = cur.fetchone()
    db_connection.commit()
    assert stored == 2


def test_patch_min_quantity_unknown_product_returns_404(admin_api):
    response = admin_api.patch("/api/products/999999/min-quantity", json={"min_quantity": 3})

    assert response.status_code == 404


def test_patch_min_quantity_rejects_negative(admin_api):
    brand_id = _make_brand(admin_api, name="PatchNegCo")
    product_id = _make_product(admin_api, brand_id, "Widget", quantity=3)["id"]

    response = admin_api.patch(
        f"/api/products/{product_id}/min-quantity", json={"min_quantity": -1}
    )

    assert response.status_code == 422


def test_patch_min_quantity_rejects_non_integer(admin_api):
    brand_id = _make_brand(admin_api, name="PatchFloatCo")
    product_id = _make_product(admin_api, brand_id, "Widget", quantity=3)["id"]

    # pydantic rejects a fractional number for an int field before the DB.
    response = admin_api.patch(
        f"/api/products/{product_id}/min-quantity", json={"min_quantity": 2.5}
    )

    assert response.status_code == 422


def test_patch_min_quantity_leaves_other_fields_untouched(admin_api):
    brand_id = _make_brand(admin_api, name="PatchKeepCo")
    created = _make_product(
        admin_api,
        brand_id,
        "Widget",
        quantity=3,
        reorder_point=10,
        price=9.99,
        min_quantity=5,
    )

    response = admin_api.patch(
        f"/api/products/{created['id']}/min-quantity", json={"min_quantity": 12}
    )
    assert response.status_code == 200

    listing = admin_api.get("/api/products", params={"search": "Widget"}).json()
    assert listing["total"] == 1
    item = listing["items"][0]
    # The single-field PATCH must not silently reset the rest of the record.
    assert item["name"] == "Widget"
    assert item["price"] == 9.99
    assert item["quantity"] == 3
    assert item["reorder_point"] == 10
    assert item["min_quantity"] == 12


# ------------------------------------------------------------------ GET /api/products (min_quantity)


def test_products_include_min_quantity_field(admin_api):
    brand_id = _make_brand(admin_api, name="ListCo")
    _make_product(admin_api, brand_id, "Alpha", quantity=5, min_quantity=7)

    body = admin_api.get("/api/products").json()

    assert body["items"]
    for item in body["items"]:
        assert isinstance(item["min_quantity"], int)
    assert body["items"][0]["min_quantity"] == 7


def test_products_sort_by_min_quantity(admin_api):
    brand_id = _make_brand(admin_api, name="SortMinCo")
    _make_product(admin_api, brand_id, "Low", quantity=5, min_quantity=3)
    _make_product(admin_api, brand_id, "High", quantity=5, min_quantity=8)
    _make_product(admin_api, brand_id, "Mid", quantity=5, min_quantity=5)

    # The new column rides the SORT_COLUMNS allowlist in both directions.
    asc = admin_api.get("/api/products", params={"sort": "min_quantity", "direction": "asc"}).json()
    assert [i["min_quantity"] for i in asc["items"]] == [3, 5, 8]

    desc = admin_api.get(
        "/api/products", params={"sort": "min_quantity", "direction": "desc"}
    ).json()
    assert [i["min_quantity"] for i in desc["items"]] == [8, 5, 3]


# ------------------------------------------------------------------ GET /api/inventory-health


def test_inventory_health_summary_counts(admin_api):
    _seed_health_dataset(admin_api)

    body = admin_api.get("/api/inventory-health").json()

    assert body["summary"] == {"total": 6, "OUT OF STOCK": 2, "LOW STOCK": 2, "IN STOCK": 2}


def test_inventory_health_orders_by_severity_then_shortage(admin_api):
    ids = _seed_health_dataset(admin_api)

    body = admin_api.get("/api/inventory-health").json()
    order = [item["product_id"] for item in body["items"]]

    # OUT OF STOCK (bigger minimum first), then LOW STOCK (bigger shortage
    # first), then IN STOCK — not the id/creation order the rows were made in.
    assert order == [
        ids["out10"],
        ids["out5"],
        ids["low_big"],
        ids["low_small"],
        ids["healthy"],
        ids["overstocked"],
    ]

    recs = {item["product_id"]: item["recommended_to_order"] for item in body["items"]}
    assert recs[ids["out10"]] == 10
    assert recs[ids["low_big"]] == 8
    assert recs[ids["low_small"]] == 4
    assert recs[ids["healthy"]] == 0
    assert recs[ids["overstocked"]] == 0


@pytest.mark.parametrize(
    "status,expected_labels",
    [
        ("OUT OF STOCK", ["out10", "out5"]),
        ("LOW STOCK", ["low_big", "low_small"]),
        ("IN STOCK", ["healthy", "overstocked"]),
    ],
)
def test_inventory_health_status_filter_narrows_report(admin_api, status, expected_labels):
    ids = _seed_health_dataset(admin_api)

    body = admin_api.get("/api/inventory-health", params={"status": status}).json()

    assert [item["product_id"] for item in body["items"]] == [ids[k] for k in expected_labels]
    # The summary is recomputed over the filtered slice only.
    assert body["summary"]["total"] == len(expected_labels)
    assert body["summary"][status] == len(expected_labels)
    for other in ("OUT OF STOCK", "LOW STOCK", "IN STOCK"):
        if other != status:
            assert body["summary"][other] == 0


def test_inventory_health_invalid_status_returns_400(admin_api):
    response = admin_api.get("/api/inventory-health", params={"status": "IN-STOCK"})

    assert response.status_code == 400
    # The error must name the valid options so callers know what to pass.
    assert "OUT OF STOCK" in response.json()["detail"]


def test_inventory_health_status_filter_is_case_sensitive(admin_api):
    # The filter matches the exact class label; lowercase must be rejected,
    # never silently treated as "no filter" (which would return everything).
    assert admin_api.get("/api/inventory-health", params={"status": "low stock"}).status_code == 400
    assert (
        admin_api.get("/api/inventory-health", params={"status": "out of stock"}).status_code == 400
    )


def test_inventory_health_requires_auth():
    fresh = TestClient(main_module.app)

    assert fresh.get("/api/inventory-health").status_code == 401


def test_inventory_health_readable_by_any_signed_in_user(admin_api, user_api):
    brand_id = _make_brand(admin_api, name="SharedCo")
    _make_product(admin_api, brand_id, "SharedItem", quantity=1, min_quantity=5)

    response = user_api.get("/api/inventory-health")

    # Replenishment is available to every signed-in user, not just admins.
    assert response.status_code == 200
    assert response.json()["summary"]["total"] == 1


def test_inventory_health_treats_null_quantity_as_out_of_stock(admin_api, db_connection):
    brand_id = _make_brand(admin_api, name="NullCo")
    _make_product(admin_api, brand_id, "Known", quantity=10, min_quantity=5)

    # A product can exist with an unknown on-hand quantity (the column is
    # nullable); the classifier must treat NULL as 0, not crash or skip it.
    with db_connection.cursor() as cur:
        cur.execute(
            "INSERT INTO products (brand_id, name, price, quantity, min_quantity) "
            "VALUES (%s, %s, %s, NULL, %s) RETURNING id",
            (brand_id, "Unknown", 1.0, 5),
        )
        unknown_id = cur.fetchone()[0]
    db_connection.commit()

    body = admin_api.get("/api/inventory-health").json()
    row = next(i for i in body["items"] if i["product_id"] == unknown_id)
    assert row["current_quantity"] == 0
    assert row["stock_status"] == "OUT OF STOCK"
    assert row["recommended_to_order"] == 5
    assert body["summary"]["OUT OF STOCK"] == 1


# ------------------------------------------------------------------ pagination


def test_inventory_health_paginates_with_global_severity_order(admin_api):
    brand_id = _make_brand(admin_api, name="PageCo")
    size = main_module.PAGE_SIZE
    n = size + 5  # more than one page
    # All LOW STOCK with an increasing shortage (min_quantity = i + 1, qty = 1,
    # so recommended_to_order == i); inserted in ascending i so creation
    # order differs from the severity order the report must produce.
    for i in range(1, n + 1):
        _make_product(admin_api, brand_id, f"P{i:02d}", quantity=1, min_quantity=i + 1)

    page1 = admin_api.get("/api/inventory-health", params={"page": 1}).json()
    assert page1["page"] == 1
    assert page1["pages"] == 2
    assert page1["total"] == n
    assert len(page1["items"]) == size
    # The summary describes the whole report, not just the current page.
    assert page1["summary"]["total"] == n
    assert page1["summary"]["LOW STOCK"] == n

    page2 = admin_api.get("/api/inventory-health", params={"page": 2}).json()
    assert page2["page"] == 2
    assert page2["pages"] == 2
    assert len(page2["items"]) == n - size

    # Severity order is global across pages: concatenating the pages yields
    # the full report sorted by descending shortage (i = n down to 1).
    shortages = [it["recommended_to_order"] for it in page1["items"] + page2["items"]]
    assert shortages == list(range(n, 0, -1))

    # A page past the end is empty but still a valid 200.
    page3 = admin_api.get("/api/inventory-health", params={"page": 3}).json()
    assert page3["items"] == []
    assert page3["pages"] == 2


def test_inventory_health_default_page_is_first_page(admin_api):
    _seed_health_dataset(admin_api)

    body = admin_api.get("/api/inventory-health").json()

    assert body["page"] == 1
    assert body["pages"] == 1
    assert body["total"] == 6
    assert len(body["items"]) == 6


def test_inventory_health_page_must_be_positive(admin_api):
    _make_brand(admin_api, name="ValCo")

    assert admin_api.get("/api/inventory-health", params={"page": 0}).status_code == 422
    assert admin_api.get("/api/inventory-health", params={"page": -1}).status_code == 422


def test_inventory_health_status_filter_composes_with_pagination(admin_api):
    brand_id = _make_brand(admin_api, name="MixCo")
    size = main_module.PAGE_SIZE
    for i in range(1, size + 3):  # size + 2 LOW STOCK products
        _make_product(admin_api, brand_id, f"L{i:02d}", quantity=1, min_quantity=5)
    _make_product(admin_api, brand_id, "Healthy", quantity=10, min_quantity=5)  # IN STOCK

    page1 = admin_api.get("/api/inventory-health", params={"status": "LOW STOCK", "page": 1}).json()
    assert page1["total"] == size + 2
    assert page1["summary"]["total"] == size + 2
    assert len(page1["items"]) == size
    assert all(it["stock_status"] == "LOW STOCK" for it in page1["items"])

    page2 = admin_api.get("/api/inventory-health", params={"status": "LOW STOCK", "page": 2}).json()
    assert len(page2["items"]) == 2


# ------------------------------------------------------------------ CSV export


def test_inventory_health_csv_requires_auth(admin_api):
    # admin_api shares its client and adds a token to it; use a brand-new
    # client for the unauthenticated check.
    fresh = TestClient(main_module.app)

    assert fresh.get("/api/export/inventory-health.csv").status_code == 401
    assert admin_api.get("/api/export/inventory-health.csv").status_code == 200


def test_inventory_health_csv_header_and_disposition(admin_api):
    response = admin_api.get("/api/export/inventory-health.csv")

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/csv")
    assert "attachment; filename=inventory-health.csv" in response.headers["content-disposition"]
    assert response.text.splitlines()[0] == (
        "Product ID,Name,Brand,Current Quantity,Minimum Quantity,"
        "Stock Status,Recommended Replenishment Quantity"
    )


def test_inventory_health_csv_rows_match_json_report(admin_api):
    ids = _seed_health_dataset(admin_api)
    json_items = admin_api.get("/api/inventory-health").json()["items"]

    response = admin_api.get("/api/export/inventory-health.csv")
    assert response.status_code == 200
    rows = list(csv.DictReader(response.text.splitlines()))

    # Same rows, same order as the JSON endpoint.
    assert [int(r["Product ID"]) for r in rows] == [i["product_id"] for i in json_items]
    for row, item in zip(rows, json_items):
        assert row["Name"] == item["name"]
        assert row["Brand"] == item["brand"]
        assert int(row["Current Quantity"]) == item["current_quantity"]
        assert int(row["Minimum Quantity"]) == item["min_quantity"]
        assert row["Stock Status"] == item["stock_status"]
        assert int(row["Recommended Replenishment Quantity"]) == item["recommended_to_order"]

    assert set(ids.values()) == {i["product_id"] for i in json_items}


def test_inventory_health_csv_escapes_names_with_comma_and_quote(admin_api):
    brand_id = _make_brand(admin_api, name="EscapeCo")
    tricky = 'Gizmo, the "Big" one'
    product_id = _make_product(admin_api, brand_id, tricky, quantity=0, min_quantity=5)["id"]
    _make_product(admin_api, brand_id, "Plain", quantity=10, min_quantity=5)

    response = admin_api.get("/api/export/inventory-health.csv")
    assert response.status_code == 200

    # csv.writer quotes the field and doubles inner quotes; that exact
    # escaped form must appear verbatim in the raw text.
    escaped_field = '"' + tricky.replace('"', '""') + '"'
    assert escaped_field in response.text

    # A DictReader must recover the original name and keep the columns
    # aligned despite the embedded comma.
    rows = list(csv.DictReader(response.text.splitlines()))
    assert tricky in [r["Name"] for r in rows]
    tricky_row = next(r for r in rows if r["Product ID"] == str(product_id))
    assert tricky_row["Stock Status"] == "OUT OF STOCK"
    assert int(tricky_row["Current Quantity"]) == 0
    assert int(tricky_row["Recommended Replenishment Quantity"]) == 5


# ------------------------------------------------------------------ independence of concepts


def test_low_stock_only_is_independent_of_min_quantity(admin_api):
    brand_id = _make_brand(admin_api, name="MixCo")
    # The quick filter keys off reorder_point; inventory health keys off
    # min_quantity. Seed products where the two disagree both ways.
    _make_product(admin_api, brand_id, "BelowReorder", quantity=2, reorder_point=10, min_quantity=5)
    _make_product(
        admin_api,
        brand_id,
        "BelowReorderButInStock",
        quantity=50,
        reorder_point=100,
        min_quantity=5,
    )
    _make_product(
        admin_api, brand_id, "AboveReorderLowMin", quantity=5, reorder_point=3, min_quantity=50
    )
    _make_product(admin_api, brand_id, "ZeroQty", quantity=0, reorder_point=10, min_quantity=5)

    response = admin_api.get("/api/products", params={"low_stock_only": "true"})
    names = [i["name"] for i in response.json()["items"]]
    # Only strictly-below-reorder-point products; min_quantity is irrelevant here.
    assert names == ["BelowReorder", "BelowReorderButInStock", "ZeroQty"]

    # Inventory health uses the other axis, so the classifications differ.
    statuses = {
        i["name"]: i["stock_status"] for i in admin_api.get("/api/inventory-health").json()["items"]
    }
    assert statuses["AboveReorderLowMin"] == "LOW STOCK"  # not in low_stock_only
    assert statuses["BelowReorderButInStock"] == "IN STOCK"  # is in low_stock_only
