from conftest import (
    ADMIN_PASSWORD,
    ADMIN_USERNAME,
    REGULAR_PASSWORD,
    REGULAR_USERNAME,
    post
)


def password_hash(db_connection, username):
    cur = db_connection.cursor()
    cur.execute(
        "SELECT password_hash FROM users WHERE username = %s",
        (username,)
    )
    return cur.fetchone()[0]


def user_id_of(db_connection, username):
    cur = db_connection.cursor()
    cur.execute("SELECT id FROM users WHERE username = %s", (username,))
    return cur.fetchone()[0]


# --- self-service change ----------------------------------------------


def test_change_password_flow(flask_app, admin_client, db_connection):
    old_hash = password_hash(db_connection, ADMIN_USERNAME)

    response = post(admin_client, "/password", data={
        "current_password": ADMIN_PASSWORD,
        "password": "brand-new-pass-1",
        "confirm": "brand-new-pass-1"
    })

    assert response.status_code == 302
    assert password_hash(db_connection, ADMIN_USERNAME) != old_hash

    client = flask_app.test_client()

    response = post(client, "/login", data={
        "username": ADMIN_USERNAME,
        "password": ADMIN_PASSWORD
    })
    assert b"Invalid username or password." in response.data

    response = post(client, "/login", data={
        "username": ADMIN_USERNAME,
        "password": "brand-new-pass-1"
    })
    assert response.status_code == 302


def test_change_password_requires_correct_current(admin_client):
    response = post(admin_client, "/password", data={
        "current_password": "totally-wrong-1",
        "password": "brand-new-pass-1",
        "confirm": "brand-new-pass-1"
    })

    assert response.status_code == 200
    assert b"Current password is incorrect." in response.data


def test_change_password_requires_long_password(admin_client):
    response = post(admin_client, "/password", data={
        "current_password": ADMIN_PASSWORD,
        "password": "short",
        "confirm": "short"
    })

    assert response.status_code == 200
    assert b"Password must be at least 8 characters." in response.data


def test_change_password_requires_matching_confirm(admin_client):
    response = post(admin_client, "/password", data={
        "current_password": ADMIN_PASSWORD,
        "password": "brand-new-pass-1",
        "confirm": "different-pass-1"
    })

    assert response.status_code == 200
    assert b"Passwords do not match." in response.data


def test_regular_users_can_change_their_own_password(
    user_client, db_connection
):
    response = post(user_client, "/password", data={
        "current_password": REGULAR_PASSWORD,
        "password": "regular-new-pass-1",
        "confirm": "regular-new-pass-1"
    })

    assert response.status_code == 302
    assert password_hash(db_connection, REGULAR_USERNAME)


def test_change_password_requires_login(flask_app, admin_client):
    client = flask_app.test_client()

    response = client.get("/password")

    assert response.status_code == 302
    assert response.headers["Location"].endswith("/login")


def test_change_password_link_in_navigation(admin_client):
    assert b"Change Password" in admin_client.get("/products").data


# --- admin reset -------------------------------------------------------


def test_admin_resets_another_password(flask_app, admin_client, db_connection):
    post(admin_client, "/users/add", data={
        "username": "resetme",
        "password": "reset-old-pass-1",
        "confirm": "reset-old-pass-1",
        "role": "user"
    })

    target_id = user_id_of(db_connection, "resetme")

    response = post(admin_client, f"/users/password?user_id={target_id}", data={
        "password": "reset-new-pass-1",
        "confirm": "reset-new-pass-1"
    })

    assert response.status_code == 302

    client = flask_app.test_client()

    response = post(client, "/login", data={
        "username": "resetme",
        "password": "reset-old-pass-1"
    })
    assert b"Invalid username or password." in response.data

    response = post(client, "/login", data={
        "username": "resetme",
        "password": "reset-new-pass-1"
    })
    assert response.status_code == 302


def test_reset_page_shows_the_account(admin_client, db_connection):
    target_id = user_id_of(db_connection, ADMIN_USERNAME)

    response = admin_client.get(f"/users/password?user_id={target_id}")

    assert response.status_code == 200
    assert b"Set Password" in response.data


def test_reset_validates_new_password(admin_client, db_connection):
    target_id = user_id_of(db_connection, ADMIN_USERNAME)

    response = post(admin_client, f"/users/password?user_id={target_id}", data={
        "password": "short",
        "confirm": "short"
    })
    assert b"Password must be at least 8 characters." in response.data

    response = post(admin_client, f"/users/password?user_id={target_id}", data={
        "password": "valid-pass-123",
        "confirm": "other-pass-123"
    })
    assert b"Passwords do not match." in response.data


def test_reset_requires_id(admin_client):
    response = post(admin_client, "/users/password", data={"password": "x"})

    assert response.status_code == 400


def test_reset_unknown_user_returns_404(admin_client):
    response = post(
        admin_client,
        "/users/password?user_id=99999",
        data={"password": "some-pass-123", "confirm": "some-pass-123"}
    )

    assert response.status_code == 404


def test_regular_users_get_403_on_reset(user_client):
    assert user_client.get("/users/password?user_id=1").status_code == 403

    assert post(user_client, "/users/password?user_id=1", data={
        "password": "sneaky-pass-123",
        "confirm": "sneaky-pass-123"
    }).status_code == 403


def test_users_list_links_to_reset(admin_client):
    assert b"Password" in admin_client.get("/users").data
