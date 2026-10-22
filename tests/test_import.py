"""
P9: POST /api/products/import — bulk product upload from CSV. Valid rows
import (with an 'import' movement per P8), duplicates are skipped, broken
rows are reported with their data-row number, and bad files are rejected
upfront.
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


HEADER = "name,brand,price,quantity\n"


def _csv(content: str, name: str = "products.csv"):
    return {"file": (name, content.encode("utf-8"), "text/csv")}


def _post_import(admin_api, content, name="products.csv"):
    return admin_api.post("/api/products/import", files=_csv(content, name))


def test_import_mixed_file_reports_all_three_buckets(api, admin_api):
    # AC: 3 valid + 1 duplicate + 1 broken -> imported=3, skipped=1, errors=1
    brand_id = admin_api.post("/api/brands", json={"name": "Acme"}).json()["id"]
    admin_api.post(
        "/api/products",
        json={"brand_id": brand_id, "name": "Existing Widget", "price": 5.0, "quantity": 4},
    )

    response = _post_import(
        admin_api,
        HEADER
        + "WidgetA,Acme,9.99,10\n"
        + "WidgetB,acme,4.50,0\n"  # qty=0: imported, no movement
        + "WidgetC,Acme,1.25,3\n"
        + "Existing Widget,ACME,2.00,5\n"  # duplicate (case-insensitive name+brand)
        + "WidgetD,Acme,free,7\n",  # broken price
    )

    assert response.status_code == 200
    body = response.json()
    assert body["imported"] == 3
    assert body["skipped"] == [{"row": 4, "reason": "duplicate"}]
    assert body["errors"] == [{"row": 5, "reason": "invalid price"}]


def test_imported_products_are_visible_in_the_list(api, admin_api):
    admin_api.post("/api/brands", json={"name": "Acme"})

    _post_import(admin_api, HEADER + "Visible Widget,Acme,7.00,2\n")

    listing = admin_api.get("/api/products", params={"search": "Visible Widget"}).json()
    assert "Visible Widget" in [p["name"] for p in listing["items"]]


def test_import_records_import_movements_only_for_positive_qty(api, admin_api):
    admin_api.post("/api/brands", json={"name": "Acme"})

    _post_import(admin_api, HEADER + "Stocked,Acme,1.00,6\nUnstocked,Acme,1.00,0\n")

    movements = admin_api.get("/api/movements", params={"limit": 100}).json()
    by_product = {m["product_id"]: m for m in movements["items"]}
    stocked = admin_api.get("/api/products", params={"search": "Stocked"}).json()["items"][0]
    unstocked = admin_api.get("/api/products", params={"search": "Unstocked"}).json()["items"][0]
    assert by_product[stocked["id"]]["reason"] == "import"
    assert by_product[stocked["id"]]["qty_delta"] == 6
    assert unstocked["id"] not in by_product


def test_import_skips_in_file_duplicates(api, admin_api):
    admin_api.post("/api/brands", json={"name": "Acme"})

    response = _post_import(admin_api, HEADER + "Twin,Acme,1.00,1\nTwin,acme,1.00,2\n")

    body = response.json()
    assert body["imported"] == 1
    assert body["skipped"] == [{"row": 2, "reason": "duplicate"}]


def test_import_unknown_brand_is_an_error_row(api, admin_api):
    admin_api.post("/api/brands", json={"name": "Acme"})

    response = _post_import(admin_api, HEADER + "Ghost,Nope,1.00,1\n")

    assert response.status_code == 200
    body = response.json()
    assert body["imported"] == 0
    assert body["errors"] == [{"row": 1, "reason": "unknown brand: Nope"}]


def test_import_accepts_bom_and_reordered_columns(api, admin_api):
    admin_api.post("/api/brands", json={"name": "Acme"})

    response = _post_import(
        admin_api,
        "\ufeffquantity,brand,name,price\n5,Acme,Bom Widget,3.00\n",
    )

    assert response.status_code == 200
    assert response.json()["imported"] == 1


def test_import_rejects_empty_and_header_only_files(api, admin_api):
    assert _post_import(admin_api, "").status_code == 400
    assert _post_import(admin_api, HEADER).status_code == 400


def test_import_rejects_wrong_extension_and_missing_columns(api, admin_api):
    response = _post_import(admin_api, HEADER + "X,Acme,1,1\n", name="products.txt")
    assert response.status_code == 400
    assert _post_import(admin_api, "name,price\nX,1\n").status_code == 400


def test_import_rejects_oversized_file(api, admin_api):
    big = "x" * (main_module.IMPORT_MAX_BYTES + 1)
    response = admin_api.post(
        "/api/products/import",
        files={"file": ("products.csv", big.encode(), "text/csv")},
    )

    assert response.status_code == 400


def test_import_rejects_more_than_1000_rows(api, admin_api):
    admin_api.post("/api/brands", json={"name": "Acme"})

    rows = HEADER + "".join(f"Row {i},Acme,1.00,1\n" for i in range(1001))
    response = _post_import(admin_api, rows)

    assert response.status_code == 400


def test_import_requires_auth(api):
    response = api.post("/api/products/import", files=_csv(HEADER + "X,Acme,1,1\n"))

    assert response.status_code == 401
