from conftest import post

def brand_id(db_connection, name):
    cur = db_connection.cursor()
    cur.execute("SELECT id FROM brands WHERE name = %s", (name,))
    return cur.fetchone()[0]


def add_product(admin_client, db_connection, brand, name,
                price="9.99", quantity="1"):
    post(admin_client, "/products/add", data={
        "brand_id": str(brand_id(db_connection, brand)),
        "name": name,
        "price": price,
        "quantity": quantity
    })

    cur = db_connection.cursor()
    cur.execute("SELECT id FROM products WHERE name = %s", (name,))
    return cur.fetchone()[0]


def product_row(db_connection, product_id):
    cur = db_connection.cursor()
    cur.execute(
        "SELECT brand_id, name, price, quantity FROM products WHERE id = %s",
        (product_id,)
    )
    return cur.fetchone()


def test_add_product_flow(admin_client, db_connection):
    post(admin_client, "/brands/add", data={"name": "Sony"})

    response = post(admin_client, "/products/add", data={
        "brand_id": str(brand_id(db_connection, "Sony")),
        "name": "Headphones",
        "price": "19.99",
        "quantity": "7"
    })

    assert response.status_code == 302

    cur = db_connection.cursor()
    cur.execute(
        "SELECT brand_id, name, price, quantity FROM products WHERE name = %s",
        ("Headphones",)
    )
    row = cur.fetchone()

    assert row is not None
    assert row[1] == "Headphones"
    assert row[3] == 7


def test_new_product_appears_in_list(admin_client, db_connection):
    post(admin_client, "/brands/add", data={"name": "ListCo"})
    add_product(admin_client, db_connection, "ListCo", "Listed Item")

    page = admin_client.get("/products").data

    assert b"Listed Item" in page
    assert b"$9.99" in page


def test_add_product_requires_brand(admin_client):
    response = post(admin_client, "/products/add", data={
        "brand_id": "",
        "name": "NoBrand",
        "price": "1",
        "quantity": "1"
    })

    assert response.status_code == 200
    assert b"Please select a brand." in response.data


def test_add_product_rejects_unknown_brand(admin_client):
    response = post(admin_client, "/products/add", data={
        "brand_id": "99999",
        "name": "GhostBrand",
        "price": "1",
        "quantity": "1"
    })

    assert response.status_code == 200
    assert b"Selected brand does not exist." in response.data


def test_add_product_requires_name(admin_client, db_connection):
    post(admin_client, "/brands/add", data={"name": "Nameless"})

    response = post(admin_client, "/products/add", data={
        "brand_id": str(brand_id(db_connection, "Nameless")),
        "name": "",
        "price": "1",
        "quantity": "1"
    })

    assert response.status_code == 200
    assert b"Product name is required." in response.data


def test_add_product_rejects_bad_price(admin_client, db_connection):
    post(admin_client, "/brands/add", data={"name": "Priceline"})
    brand = str(brand_id(db_connection, "Priceline"))

    response = post(admin_client, "/products/add", data={
        "brand_id": brand,
        "name": "Priced",
        "price": "abc",
        "quantity": "1"
    })

    assert response.status_code == 200
    assert b"Price must be a number." in response.data

    response = post(admin_client, "/products/add", data={
        "brand_id": brand,
        "name": "Priced",
        "price": "-5",
        "quantity": "1"
    })

    assert response.status_code == 200
    assert b"Price must be a non-negative number." in response.data


def test_add_product_rejects_bad_quantity(admin_client, db_connection):
    post(admin_client, "/brands/add", data={"name": "Stockline"})
    brand = str(brand_id(db_connection, "Stockline"))

    response = post(admin_client, "/products/add", data={
        "brand_id": brand,
        "name": "Quantified",
        "price": "1",
        "quantity": "2.5"
    })

    assert response.status_code == 200
    assert b"Quantity must be an integer." in response.data

    response = post(admin_client, "/products/add", data={
        "brand_id": brand,
        "name": "Quantified",
        "price": "1",
        "quantity": "-3"
    })

    assert response.status_code == 200
    assert b"Quantity must be a non-negative integer." in response.data


def test_edit_product_flow(admin_client, db_connection):
    post(admin_client, "/brands/add", data={"name": "EditCo"})
    product_id = add_product(
        admin_client, db_connection, "EditCo", "OldName", "10.00", "4"
    )

    assert admin_client.get("/products/edit").status_code == 200
    assert admin_client.get(
        f"/products/edit?brand_id={brand_id(db_connection, 'EditCo')}"
    ).status_code == 200

    response = post(admin_client, f"/products/edit?product_id={product_id}", data={
        "name": "NewName",
        "price": "12.50",
        "quantity": "9"
    })

    assert response.status_code == 302

    row = product_row(db_connection, product_id)

    assert row[1] == "NewName"
    assert str(row[2]) == "12.50"
    assert row[3] == 9


def test_edit_product_unknown_returns_404(admin_client):
    assert admin_client.get(
        "/products/edit?product_id=99999"
    ).status_code == 404
    assert post(admin_client, "/products/edit?product_id=99999", data={
        "name": "X", "price": "1", "quantity": "1"
    }).status_code == 404


def test_edit_product_requires_id(admin_client):
    response = post(admin_client, "/products/edit", data={
        "name": "X", "price": "1", "quantity": "1"
    })

    assert response.status_code == 400


def test_delete_product_flow(admin_client, db_connection):
    post(admin_client, "/brands/add", data={"name": "DelCo"})
    product_id = add_product(
        admin_client, db_connection, "DelCo", "Doomed", "1.00", "1"
    )

    response = admin_client.get(f"/products/delete?product_id={product_id}")
    assert response.status_code == 200
    assert b"Are you sure you want to delete this product?" in response.data

    response = post(admin_client, f"/products/delete?product_id={product_id}")
    assert response.status_code == 302

    assert product_row(db_connection, product_id) is None


def test_delete_product_requires_id(admin_client):
    response = post(admin_client, "/products/delete")

    assert response.status_code == 400


def test_delete_product_unknown_returns_404(admin_client):
    response = post(admin_client, "/products/delete?product_id=99999")

    assert response.status_code == 404


def test_search_filters_by_name_and_brand(admin_client, db_connection):
    post(admin_client, "/brands/add", data={"name": "Acme"})
    post(admin_client, "/brands/add", data={"name": "Beta"})
    add_product(admin_client, db_connection, "Acme", "Widget", "1", "1")
    add_product(admin_client, db_connection, "Beta", "Gadget", "1", "1")

    page = admin_client.get(
        "/products", query_string={"search": "widget"}
    ).data

    assert b"Widget" in page
    assert b"Gadget" not in page

    page = admin_client.get(
        "/products", query_string={"search": "acme"}
    ).data

    assert b"Widget" in page
    assert b"Gadget" not in page


def test_search_with_no_matches_shows_empty_state(admin_client):
    page = admin_client.get(
        "/products", query_string={"search": "nothing-matches"}
    ).data

    assert b"No products found." in page


def test_search_treats_wildcards_literally(admin_client, db_connection):
    post(admin_client, "/brands/add", data={"name": "WildCo"})
    add_product(admin_client, db_connection, "WildCo", "100%_pure", "1", "1")
    add_product(admin_client, db_connection, "WildCo", "Ordinary Soap", "1", "1")

    page = admin_client.get(
        "/products", query_string={"search": "%_"}
    ).data

    assert b"100%_pure" in page
    assert b"Ordinary Soap" not in page


def test_sorting_orders_products(admin_client, db_connection):
    post(admin_client, "/brands/add", data={"name": "SortCo"})
    add_product(admin_client, db_connection, "SortCo", "Banana", "5.00", "1")
    add_product(admin_client, db_connection, "SortCo", "Apple", "9.00", "1")
    add_product(admin_client, db_connection, "SortCo", "Cherry", "1.00", "1")

    page = admin_client.get(
        "/products", query_string={"sort": "name", "order": "asc"}
    ).data
    assert page.index(b"Apple") < page.index(b"Banana") < page.index(b"Cherry")

    page = admin_client.get(
        "/products", query_string={"sort": "name", "order": "desc"}
    ).data
    assert page.index(b"Cherry") < page.index(b"Banana") < page.index(b"Apple")

    page = admin_client.get(
        "/products", query_string={"sort": "price", "order": "desc"}
    ).data
    assert page.index(b"Apple") < page.index(b"Banana") < page.index(b"Cherry")


def test_unknown_sort_key_falls_back_to_default_order(admin_client):
    response = admin_client.get(
        "/products",
        query_string={"sort": "name; DROP TABLE products;--"}
    )

    assert response.status_code == 200


def test_pagination_splits_pages(admin_client, db_connection):
    post(admin_client, "/brands/add", data={"name": "PageCo"})

    for index in range(1, 8):
        add_product(
            admin_client, db_connection,
            "PageCo", f"Pager {index:02d}", "1", "1"
        )

    page1 = admin_client.get("/products").data
    assert b"Pager 01" in page1
    assert b"Pager 05" in page1
    assert b"Pager 06" not in page1

    page2 = admin_client.get(
        "/products", query_string={"page": 2}
    ).data
    assert b"Pager 06" in page2
    assert b"Pager 07" in page2
    assert b"Pager 01" not in page2

    invalid_page = admin_client.get(
        "/products", query_string={"page": 0}
    ).data
    assert b"Pager 01" in invalid_page


def test_csv_export_contains_all_products(admin_client, db_connection):
    post(admin_client, "/brands/add", data={"name": "CsvCo"})
    add_product(admin_client, db_connection, "CsvCo", "Exported Item", "3.50", "2")

    response = admin_client.get("/products/export")

    assert response.status_code == 200
    assert response.headers["Content-Type"].startswith("text/csv")
    assert "attachment" in response.headers["Content-Disposition"]

    lines = response.get_data(as_text=True).strip().splitlines()
    assert lines[0] == "ID,Brand,Product,Price,Quantity"
    assert any("Exported Item" in line for line in lines)


def test_csv_export_honors_search_filter(admin_client, db_connection):
    post(admin_client, "/brands/add", data={"name": "CsvFilter"})
    add_product(admin_client, db_connection, "CsvFilter", "KeepThis", "1", "1")
    add_product(admin_client, db_connection, "CsvFilter", "DropThat", "1", "1")

    text = admin_client.get(
        "/products/export", query_string={"search": "KeepThis"}
    ).get_data(as_text=True)

    assert "KeepThis" in text
    assert "DropThat" not in text
