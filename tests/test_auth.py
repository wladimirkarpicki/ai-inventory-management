from conftest import ADMIN_PASSWORD, ADMIN_USERNAME


def test_fresh_install_redirects_to_setup(client):
    response = client.get("/products")

    assert response.status_code == 302
    assert response.headers["Location"].endswith("/setup")


def test_setup_creates_first_admin(client):
    response = client.post("/setup", data={
        "username": "first",
        "password": "first-pass-123",
        "confirm": "first-pass-123"
    })

    assert response.status_code == 302
    assert response.headers["Location"].endswith("/login")

    response = client.post("/login", data={
        "username": "first",
        "password": "first-pass-123"
    })

    assert response.status_code == 302
    assert response.headers["Location"].endswith("/")


def test_setup_closes_once_a_user_exists(admin_client):
    response = admin_client.get("/setup")

    assert response.status_code == 302
    assert response.headers["Location"].endswith("/login")


def test_login_rejects_wrong_password(admin_client, flask_app):
    client = flask_app.test_client()

    response = client.post("/login", data={
        "username": ADMIN_USERNAME,
        "password": "wrong-pass-123"
    })

    assert response.status_code == 200
    assert b"Invalid username or password." in response.data

    response = client.get("/products")
    assert response.status_code == 302


def test_login_rejects_unknown_user(admin_client, flask_app):
    client = flask_app.test_client()

    response = client.post("/login", data={
        "username": "ghost-user",
        "password": "whatever-123"
    })

    assert response.status_code == 200
    assert b"Invalid username or password." in response.data


def test_logout_ends_session(admin_client):
    response = admin_client.get("/logout")

    assert response.status_code == 302
    assert response.headers["Location"].endswith("/login")

    response = admin_client.get("/products")
    assert response.status_code == 302


def test_guests_are_sent_to_login_when_users_exist(admin_client, flask_app):
    client = flask_app.test_client()

    for path in ("/", "/products", "/brands", "/products/export", "/users"):
        response = client.get(path)

        assert response.status_code == 302
        assert response.headers["Location"].endswith("/login")


def test_setup_requires_matching_password(client):
    response = client.post("/setup", data={
        "username": "mismatch",
        "password": "one-pass-123",
        "confirm": "other-pass-123"
    })

    assert response.status_code == 200
    assert b"Passwords do not match." in response.data


def test_setup_requires_long_password(client):
    response = client.post("/setup", data={
        "username": "shorty",
        "password": "short",
        "confirm": "short"
    })

    assert response.status_code == 200
    assert b"Password must be at least 8 characters." in response.data


def test_setup_requires_username(client):
    response = client.post("/setup", data={
        "username": "",
        "password": "valid-pass-123",
        "confirm": "valid-pass-123"
    })

    assert response.status_code == 200
    assert b"Username is required." in response.data


def test_login_page_renders_for_guests(client):
    response = client.get("/login")

    assert response.status_code == 200
    assert b"Sign in" in response.data or b"Login" in response.data
