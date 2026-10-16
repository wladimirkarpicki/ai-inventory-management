from markupsafe import escape

from conftest import post


def brand_id(db_connection, name):
    cur = db_connection.cursor()
    cur.execute("SELECT id FROM brands WHERE name = %s", (name,))
    return cur.fetchone()[0]


def test_add_brand_flow(admin_client, db_connection):
    response = post(admin_client, "/brands/add", data={"name": "UniqueBrand"})

    assert response.status_code == 302

    cur = db_connection.cursor()
    cur.execute("SELECT name FROM brands WHERE name = 'UniqueBrand'")
    assert cur.fetchone() is not None


def test_add_brand_duplicate_is_case_insensitive(admin_client):
    post(admin_client, "/brands/add", data={"name": "Sony"})

    response = post(admin_client, 
        "/brands/add", data={"name": "sony"}
    )

    assert response.status_code == 200
    assert str(escape('A brand named "sony" already exists.')).encode() in response.data


def test_add_brand_requires_name(admin_client):
    response = post(admin_client, "/brands/add", data={"name": ""})

    assert response.status_code == 200
    assert b"Brand name is required." in response.data


def test_add_brand_rejects_long_name(admin_client):
    response = post(admin_client, "/brands/add", data={"name": "x" * 101})

    assert response.status_code == 200
    assert b"Brand name must be 100 characters or fewer." in response.data


def test_edit_brand_flow(admin_client, db_connection):
    post(admin_client, "/brands/add", data={"name": "OldName"})
    target_id = brand_id(db_connection, "OldName")

    assert admin_client.get("/brands/edit").status_code == 200
    assert admin_client.get(
        f"/brands/edit?brand_id={target_id}"
    ).status_code == 200

    response = post(admin_client, 
        f"/brands/edit?brand_id={target_id}",
        data={"name": "NewName"}
    )

    assert response.status_code == 302

    cur = db_connection.cursor()
    cur.execute("SELECT name FROM brands WHERE id = %s", (target_id,))
    assert cur.fetchone()[0] == "NewName"


def test_edit_brand_rejects_duplicate_name(admin_client, db_connection):
    post(admin_client, "/brands/add", data={"name": "Alpha"})
    post(admin_client, "/brands/add", data={"name": "Beta"})

    alpha_id = brand_id(db_connection, "Alpha")

    response = post(admin_client, 
        f"/brands/edit?brand_id={alpha_id}",
        data={"name": "beta"}
    )

    assert response.status_code == 200
    assert str(escape('A brand named "beta" already exists.')).encode() in response.data

    cur = db_connection.cursor()
    cur.execute("SELECT name FROM brands WHERE id = %s", (alpha_id,))
    assert cur.fetchone()[0] == "Alpha"


def test_edit_brand_unknown_returns_404(admin_client):
    assert admin_client.get(
        "/brands/edit?brand_id=99999"
    ).status_code == 404
    assert post(admin_client, 
        "/brands/edit?brand_id=99999", data={"name": "X"}
    ).status_code == 404


def test_delete_brand_with_products_is_blocked(
    admin_client, db_connection
):
    post(admin_client, "/brands/add", data={"name": "FullHouse"})
    target_id = brand_id(db_connection, "FullHouse")

    post(admin_client, "/products/add", data={
        "brand_id": str(target_id),
        "name": "Blocking Product",
        "price": "1.00",
        "quantity": "1"
    })

    response = post(admin_client, 
        f"/brands/delete?brand_id={target_id}"
    )

    assert response.status_code == 200
    assert b"This brand has products and cannot be deleted." in response.data

    cur = db_connection.cursor()
    cur.execute("SELECT name FROM brands WHERE id = %s", (target_id,))
    assert cur.fetchone() is not None


def test_delete_empty_brand_flow(admin_client, db_connection):
    post(admin_client, "/brands/add", data={"name": "Empty"})
    target_id = brand_id(db_connection, "Empty")

    response = admin_client.get(f"/brands/delete?brand_id={target_id}")
    assert response.status_code == 200
    assert b"Are you sure you want to delete this brand?" in response.data

    response = post(admin_client, f"/brands/delete?brand_id={target_id}")
    assert response.status_code == 302

    cur = db_connection.cursor()
    cur.execute("SELECT COUNT(*) FROM brands WHERE id = %s", (target_id,))
    assert cur.fetchone()[0] == 0


def test_delete_brand_requires_id(admin_client):
    response = post(admin_client, "/brands/delete")

    assert response.status_code == 400


def test_delete_brand_unknown_returns_404(admin_client):
    response = post(admin_client, "/brands/delete?brand_id=99999")

    assert response.status_code == 404


def test_brand_list_shows_product_counts(admin_client, db_connection):
    post(admin_client, "/brands/add", data={"name": "Counter"})
    target_id = brand_id(db_connection, "Counter")

    post(admin_client, "/products/add", data={
        "brand_id": str(target_id),
        "name": "Counted Item",
        "price": "2.00",
        "quantity": "2"
    })

    page = admin_client.get("/brands").data

    assert b"Counter" in page
    assert b"Counted Item" not in page
