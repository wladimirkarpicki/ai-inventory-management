import os
import secrets
import sys
import uuid
from pathlib import Path

import psycopg
import pytest
from dotenv import load_dotenv

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

load_dotenv(os.path.join(REPO_ROOT, ".env"))

os.environ.setdefault("SECRET_KEY", "pytest-secret-key")

TEST_DB = f"ims_pytest_{uuid.uuid4().hex[:8]}"

DB_HOST = os.getenv("DATABASE_HOST")
DB_USER = os.getenv("DATABASE_USER")
DB_PASSWORD = os.getenv("DATABASE_PASSWORD")

ADMIN_CONN_STRING = f"postgresql://{DB_USER}:{DB_PASSWORD}@{DB_HOST}/postgres"
TEST_CONN_STRING = f"postgresql://{DB_USER}:{DB_PASSWORD}@{DB_HOST}/{TEST_DB}"

ADMIN_USERNAME = "admin"
ADMIN_PASSWORD = "admin-pass-123"

REGULAR_USERNAME = "regular"
REGULAR_PASSWORD = "regular-pass-123"


def _create_test_database():
    """
    Create a throwaway database from schema.sql and point the app at it.
    The database configured in .env is never touched.
    """

    conn = psycopg.connect(ADMIN_CONN_STRING, autocommit=True)
    cur = conn.cursor()
    cur.execute(f"CREATE DATABASE {TEST_DB}")
    conn.close()

    conn = psycopg.connect(TEST_CONN_STRING)
    cur = conn.cursor()

    with open(REPO_ROOT / "schema.sql", encoding="utf-8") as schema_file:
        cur.execute(schema_file.read())

    conn.commit()
    conn.close()

    os.environ["DATABASE_NAME"] = TEST_DB


def _drop_test_database():
    conn = psycopg.connect(ADMIN_CONN_STRING, autocommit=True)
    cur = conn.cursor()
    cur.execute(f"DROP DATABASE {TEST_DB}")
    conn.close()


def _clean_tables():
    """
    Empty every table before each test so tests stay independent.
    """

    conn = psycopg.connect(TEST_CONN_STRING)
    cur = conn.cursor()
    cur.execute("TRUNCATE users, products, brands RESTART IDENTITY CASCADE")
    conn.commit()
    conn.close()


def _csrf_token(client):
    """
    Mirror of the app context processor: make sure the session
    carries a CSRF token and return it.
    """

    with client.session_transaction() as sess:
        if "csrf_token" not in sess:
            sess["csrf_token"] = secrets.token_hex(32)

        return sess["csrf_token"]


def post(client, url, data=None, **kwargs):
    """
    POST helper that attaches the per-session CSRF token, the way
    the rendered forms would.
    """

    data = dict(data or {})
    data.setdefault("csrf_token", _csrf_token(client))

    return client.post(url, data=data, **kwargs)


@pytest.fixture(scope="session", autouse=True)
def _database():
    _create_test_database()

    yield

    _drop_test_database()


@pytest.fixture(autouse=True)
def _clean_tables_per_test():
    _clean_tables()


@pytest.fixture(autouse=True)
def _reset_failed_logins():
    """
    Login rate limiting keeps in-process state; keep it out of
    the way of unrelated tests.
    """

    import app as app_module

    app_module._failed_logins.clear()

    yield

    app_module._failed_logins.clear()


@pytest.fixture()
def db_connection():
    """
    Direct connection to the throwaway database, for verifying
    what the application actually wrote.
    """

    conn = psycopg.connect(TEST_CONN_STRING)

    yield conn

    conn.close()


@pytest.fixture()
def flask_app():
    import app as app_module

    app_module.app.config["TESTING"] = True

    return app_module.app


@pytest.fixture()
def client(flask_app):
    return flask_app.test_client()


@pytest.fixture()
def admin_client(flask_app):
    """
    A client signed in as the first account, which is an admin.
    """

    client = flask_app.test_client()

    post(client, "/setup", data={
        "username": ADMIN_USERNAME,
        "password": ADMIN_PASSWORD,
        "confirm": ADMIN_PASSWORD
    })

    post(client, "/login", data={
        "username": ADMIN_USERNAME,
        "password": ADMIN_PASSWORD
    })

    return client


@pytest.fixture()
def user_client(flask_app, admin_client):
    """
    A second client signed in as a regular user created by the admin.
    """

    post(admin_client, "/users/add", data={
        "username": REGULAR_USERNAME,
        "password": REGULAR_PASSWORD,
        "confirm": REGULAR_PASSWORD,
        "role": "user"
    })

    client = flask_app.test_client()

    post(client, "/login", data={
        "username": REGULAR_USERNAME,
        "password": REGULAR_PASSWORD
    })

    return client
