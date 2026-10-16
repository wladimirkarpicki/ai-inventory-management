from markupsafe import escape

from conftest import post

from conftest import ADMIN_USERNAME


def add_user(admin_client, username, password="new-pass-123", role="user"):
    return post(admin_client, "/users/add", data={
        "username": username,
        "password": password,
        "confirm": password,
        "role": role
    })


def user_row(db_connection, username):
    cur = db_connection.cursor()
    cur.execute(
        "SELECT id, username, role FROM users WHERE username = %s",
        (username,)
    )
    return cur.fetchone()


def test_add_user_creates_loginable_account(
    admin_client, flask_app, db_connection
):
    response = add_user(admin_client, "newcomer")

    assert response.status_code == 302
    assert response.headers["Location"].endswith("/users")

    row = user_row(db_connection, "newcomer")
    assert row is not None
    assert row[2] == "user"

    client = flask_app.test_client()

    response = post(client, "/login", data={
        "username": "newcomer",
        "password": "new-pass-123"
    })

    assert response.status_code == 302


def test_add_user_rejects_duplicate_username(admin_client, db_connection):
    add_user(admin_client, "twin")

    response = add_user(admin_client, "twin")

    assert response.status_code == 200
    assert str(escape('A user named "twin" already exists.')).encode() in response.data

    row = user_row(db_connection, "twin")
    assert row is not None


def test_add_user_rejects_short_password(admin_client):
    response = post(admin_client, "/users/add", data={
        "username": "shortpass",
        "password": "short",
        "confirm": "short",
        "role": "user"
    })

    assert response.status_code == 200
    assert b"Password must be at least 8 characters." in response.data


def test_add_user_rejects_mismatched_confirm(admin_client):
    response = post(admin_client, "/users/add", data={
        "username": "mismatched",
        "password": "one-pass-123",
        "confirm": "two-pass-123",
        "role": "user"
    })

    assert response.status_code == 200
    assert b"Passwords do not match." in response.data


def test_add_user_rejects_unknown_role(admin_client):
    response = post(admin_client, "/users/add", data={
        "username": "roleless",
        "password": "some-pass-123",
        "confirm": "some-pass-123",
        "role": "superadmin"
    })

    assert response.status_code == 200
    assert b"Invalid role." in response.data


def test_add_user_can_create_admin(admin_client, db_connection):
    add_user(admin_client, "secondadmin", role="admin")

    row = user_row(db_connection, "secondadmin")

    assert row is not None
    assert row[2] == "admin"


def test_role_change_cycle(admin_client, db_connection):
    add_user(admin_client, "switcher")
    target_id = user_row(db_connection, "switcher")[0]

    response = post(admin_client, 
        f"/users/edit?user_id={target_id}",
        data={"role": "admin"}
    )

    assert response.status_code == 302
    assert user_row(db_connection, "switcher")[2] == "admin"

    response = post(admin_client, 
        f"/users/edit?user_id={target_id}",
        data={"role": "user"}
    )

    assert response.status_code == 302
    assert user_row(db_connection, "switcher")[2] == "user"


def test_last_admin_cannot_be_demoted(admin_client, db_connection):
    admin_id = user_row(db_connection, ADMIN_USERNAME)[0]

    response = post(admin_client, 
        f"/users/edit?user_id={admin_id}",
        data={"role": "user"},
        follow_redirects=True
    )

    assert b"Cannot demote the last admin." in response.data
    assert user_row(db_connection, ADMIN_USERNAME)[2] == "admin"


def test_edit_user_rejects_unknown_role(admin_client, db_connection):
    add_user(admin_client, "stable")
    target_id = user_row(db_connection, "stable")[0]

    response = post(admin_client, 
        f"/users/edit?user_id={target_id}",
        data={"role": "owner"},
        follow_redirects=True
    )

    assert b"Invalid role." in response.data
    assert user_row(db_connection, "stable")[2] == "user"


def test_edit_user_requires_id(admin_client):
    response = post(admin_client, "/users/edit", data={"role": "admin"})

    assert response.status_code == 400


def test_edit_user_unknown_returns_404(admin_client):
    response = admin_client.get("/users/edit?user_id=99999")

    assert response.status_code == 404


def test_delete_confirmation_page(admin_client, db_connection):
    add_user(admin_client, "pending")
    target_id = user_row(db_connection, "pending")[0]

    response = admin_client.get(f"/users/delete?user_id={target_id}")

    assert response.status_code == 200
    assert b"Are you sure you want to delete this user account?" in response.data


def test_delete_user_removes_account(admin_client, db_connection):
    add_user(admin_client, "disposable")
    target_id = user_row(db_connection, "disposable")[0]

    response = post(admin_client, f"/users/delete?user_id={target_id}")

    assert response.status_code == 302
    assert user_row(db_connection, "disposable") is None


def test_admin_cannot_delete_own_account(admin_client, db_connection):
    admin_id = user_row(db_connection, ADMIN_USERNAME)[0]

    response = post(admin_client, 
        f"/users/delete?user_id={admin_id}",
        follow_redirects=True
    )

    assert b"You cannot delete your own account." in response.data
    assert user_row(db_connection, ADMIN_USERNAME) is not None


def test_delete_user_requires_id(admin_client):
    response = post(admin_client, "/users/delete")

    assert response.status_code == 400


def test_delete_user_unknown_returns_404(admin_client):
    response = post(admin_client, "/users/delete?user_id=99999")

    assert response.status_code == 404


def test_regular_users_get_403_on_user_pages(user_client):
    assert user_client.get("/users").status_code == 403
    assert user_client.get("/users/add").status_code == 403

    assert post(user_client, "/users/add", data={
        "username": "sneaky",
        "password": "sneaky-pass-123",
        "confirm": "sneaky-pass-123",
        "role": "admin"
    }).status_code == 403

    assert user_client.get("/users/edit?user_id=1").status_code == 403
    assert post(user_client, 
        "/users/edit?user_id=1", data={"role": "admin"}
    ).status_code == 403

    assert user_client.get("/users/delete?user_id=1").status_code == 403
    assert post(user_client, "/users/delete?user_id=1").status_code == 403


def test_regular_users_keep_inventory_access(user_client):
    assert user_client.get("/").status_code == 200
    assert user_client.get("/products").status_code == 200
    assert user_client.get("/brands").status_code == 200


def test_guests_are_redirected_on_user_pages(flask_app, admin_client):
    client = flask_app.test_client()

    for path in (
        "/users",
        "/users/add",
        "/users/edit?user_id=1",
        "/users/delete?user_id=1"
    ):
        response = client.get(path)

        assert response.status_code == 302
        assert response.headers["Location"].endswith("/login")
