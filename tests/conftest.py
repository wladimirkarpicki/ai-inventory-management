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

os.environ.setdefault("SECRET_KEY", secrets.token_hex(32))

TEST_DB = f'ims_pytest_{uuid.uuid4().hex[:8]}'

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
    cur.execute(f'CREATE DATABASE "{TEST_DB}"')
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
    cur.execute(f'DROP DATABASE "{TEST_DB}"')
    conn.close()


def _clean_tables():
    """
    Empty every table before each test so tests stay independent.
    """

    conn = psycopg.connect(TEST_CONN_STRING)
    cur = conn.cursor()
    cur.execute('TRUNCATE users, products, brands RESTART IDENTITY CASCADE')
    conn.commit()
    conn.close()


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
    Login rate limiting keeps in-process state in the FastAPI app; keep it
    out of the way of unrelated tests.
    """

    import main as main_module

    main_module._failed_logins.clear()

    yield

    main_module._failed_logins.clear()


@pytest.fixture()
def db_connection():
    """
    Direct connection to the throwaway database, for verifying
    what the application actually wrote.
    """

    conn = psycopg.connect(TEST_CONN_STRING)

    yield conn

    conn.close()