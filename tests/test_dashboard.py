import re

from test_products import add_product


def stat_value(page_text, label):
    """
    Extract the value shown in the stat card with the given label.
    """

    pattern = re.compile(
        r"stat-value\">\s*([^<]*?)\s*</div>\s*"
        r'<div class="stat-label">\s*' + re.escape(label)
    )

    match = pattern.search(page_text)

    assert match is not None, f"stat card '{label}' not found"

    return match.group(1)


def test_dashboard_shows_zeroes_on_empty_inventory(admin_client):
    response = admin_client.get("/")

    assert response.status_code == 200
    text = response.get_data(as_text=True)

    assert stat_value(text, "Products") == "0"
    assert stat_value(text, "Brands") == "0"
    assert stat_value(text, "Units in stock") == "0"
    assert stat_value(text, "Inventory value") == "$0.00"
    assert stat_value(text, "Low stock (5 or fewer units)") == "0"


def test_dashboard_aggregates_inventory(admin_client, db_connection):
    admin_client.post("/brands/add", data={"name": "DashA"})
    admin_client.post("/brands/add", data={"name": "DashB"})
    add_product(admin_client, db_connection, "DashA", "Dash Item A", "10.00", "2")
    add_product(admin_client, db_connection, "DashB", "Dash Item B", "5.00", "3")

    text = admin_client.get("/").get_data(as_text=True)

    assert stat_value(text, "Products") == "2"
    assert stat_value(text, "Brands") == "2"
    assert stat_value(text, "Units in stock") == "5"
    assert stat_value(text, "Inventory value") == "$35.00"
    assert stat_value(text, "Low stock (5 or fewer units)") == "2"


def test_dashboard_low_stock_threshold(admin_client, db_connection):
    admin_client.post("/brands/add", data={"name": "LowCo"})
    add_product(admin_client, db_connection, "LowCo", "Low Item", "1.00", "5")
    add_product(admin_client, db_connection, "LowCo", "High Item", "1.00", "6")

    text = admin_client.get("/").get_data(as_text=True)

    assert stat_value(text, "Low stock (5 or fewer units)") == "1"
