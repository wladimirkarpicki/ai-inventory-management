import time

from conftest import (
    ADMIN_PASSWORD,
    ADMIN_USERNAME,
    REGULAR_PASSWORD,
    REGULAR_USERNAME,
    post
)


# --- CSRF ---------------------------------------------------------------

def test_post_without_token_is_rejected(flask_app, admin_client):
    client = flask_app.test_client()

    response = client.post("/login", data={
        "username": ADMIN_USERNAME,
        "password": ADMIN_PASSWORD
    })

    assert response.status_code == 400
    assert b"Missing or invalid CSRF token." in response.data


def test_post_with_forged_token_is_rejected(flask_app, admin_client):
    client = flask_app.test_client()

    response = client.post("/login", data={
        "username": ADMIN_USERNAME,
        "password": ADMIN_PASSWORD,
        "csrf_token": "forged-by-attacker"
    })

    assert response.status_code == 400
    assert b"Missing or invalid CSRF token." in response.data


def test_post_with_session_token_is_accepted(flask_app, admin_client):
    client = flask_app.test_client()

    response = post(client, "/login", data={
        "username": ADMIN_USERNAME,
        "password": ADMIN_PASSWORD
    })

    assert response.status_code == 302
    assert client.get("/products").status_code == 200


def test_setup_form_embeds_token(client):
    # the setup page is only reachable while no user exists yet
    assert b'name="csrf_token"' in client.get("/setup").data


def test_rendered_forms_embed_the_token(flask_app, admin_client):
    guest = flask_app.test_client()

    assert b'name="csrf_token"' in guest.get("/login").data
    assert b'name="csrf_token"' in admin_client.get("/users/add").data
    assert b'name="csrf_token"' in admin_client.get("/products/add").data
    assert b'name="csrf_token"' in admin_client.get("/brands/add").data


def test_csrf_protects_every_post_route(flask_app, admin_client):
    """
    A POST without a token must never reach a route, whatever
    the endpoint is.
    """

    client = flask_app.test_client()

    endpoints = [
        "/setup",
        "/login",
        "/products/add",
        "/products/delete?product_id=1",
        "/brands/add",
        "/brands/edit?brand_id=1",
        "/brands/delete?brand_id=1",
    ]

    for url in endpoints:
        response = client.post(url, data={"name": "x"})

        assert response.status_code == 400, url


# --- login rate limiting -------------------------------------------------

def test_login_locks_after_repeated_failures(flask_app, admin_client):
    client = flask_app.test_client()

    for _ in range(5):
        response = post(client, "/login", data={
            "username": ADMIN_USERNAME,
            "password": "wrong-pass-123"
        })
        assert b"Invalid username or password." in response.data

    response = post(client, "/login", data={
        "username": ADMIN_USERNAME,
        "password": ADMIN_PASSWORD
    })

    assert b"Too many failed attempts." in response.data
    assert client.get("/products").status_code == 302


def test_successful_login_resets_the_counter(flask_app, admin_client):
    client = flask_app.test_client()

    for _ in range(4):
        post(client, "/login", data={
            "username": ADMIN_USERNAME,
            "password": "wrong-pass-123"
        })

    assert post(client, "/login", data={
        "username": ADMIN_USERNAME,
        "password": ADMIN_PASSWORD
    }).status_code == 302

    client.get("/logout")

    for _ in range(4):
        post(client, "/login", data={
            "username": ADMIN_USERNAME,
            "password": "wrong-pass-123"
        })

    # without the reset these would be attempts 5-8 and the
    # account would be locked; it is not.
    response = post(client, "/login", data={
        "username": ADMIN_USERNAME,
        "password": ADMIN_PASSWORD
    })

    assert response.status_code == 302


def test_lockout_expires_after_the_window(monkeypatch, flask_app, admin_client):
    import app as app_module

    monkeypatch.setattr(app_module, "LOGIN_LOCKOUT_SECONDS", 0.2)

    client = flask_app.test_client()

    for _ in range(5):
        post(client, "/login", data={
            "username": ADMIN_USERNAME,
            "password": "wrong-pass-123"
        })

    response = post(client, "/login", data={
        "username": ADMIN_USERNAME,
        "password": ADMIN_PASSWORD
    })
    assert b"Too many failed attempts." in response.data

    time.sleep(0.3)

    response = post(client, "/login", data={
        "username": ADMIN_USERNAME,
        "password": ADMIN_PASSWORD
    })
    assert response.status_code == 302


def test_lockout_only_affects_that_account(flask_app, admin_client):
    client = flask_app.test_client()

    for _ in range(5):
        post(client, "/login", data={
            "username": ADMIN_USERNAME,
            "password": "wrong-pass-123"
        })

    # the regular user still signs in normally
    post(admin_client, "/users/add", data={
        "username": REGULAR_USERNAME,
        "password": REGULAR_PASSWORD,
        "confirm": REGULAR_PASSWORD,
        "role": "user"
    })

    second = flask_app.test_client()

    response = post(second, "/login", data={
        "username": REGULAR_USERNAME,
        "password": REGULAR_PASSWORD
    })

    assert response.status_code == 302


# --- deleted account sessions --------------------------------------------

def test_deleted_account_session_is_invalidated(
    admin_client, user_client, db_connection
):
    assert user_client.get("/products").status_code == 200

    cur = db_connection.cursor()
    cur.execute(
        "SELECT id FROM users WHERE username = %s",
        (REGULAR_USERNAME,)
    )
    regular_id = cur.fetchone()[0]

    response = post(admin_client, f"/users/delete?user_id={regular_id}")

    assert response.status_code == 302

    # the deleted user's ghost session no longer grants access
    response = user_client.get("/products")

    assert response.status_code == 302
    assert response.headers["Location"].endswith("/login")
