"""
Inventory Management System - FastAPI JSON API.

Replaces the Flask JSON layer for the React SPA. The signed-in
identity travels as a bearer token; every request re-checks the
account in the database, so tokens of deleted accounts stop
working immediately.
"""

import csv
import io
import json
import os
import time
import urllib.request
from collections.abc import Iterator
from datetime import UTC, datetime, timedelta
from decimal import Decimal, InvalidOperation
from pathlib import Path

import jwt
import psycopg
from dotenv import load_dotenv
from fastapi import Depends, FastAPI, File, HTTPException, Query, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, StreamingResponse
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from fastapi.staticfiles import StaticFiles
from prometheus_fastapi_instrumentator import Instrumentator
from pydantic import BaseModel, Field
from werkzeug.security import check_password_hash, generate_password_hash

from database import get_connection_string

load_dotenv()

SECRET_KEY = os.getenv("SECRET_KEY")

if not SECRET_KEY:
    raise RuntimeError("SECRET_KEY is not set. Add SECRET_KEY=<random value> to your .env file.")

if len(SECRET_KEY) < 32:
    raise RuntimeError(
        "SECRET_KEY is too short. Generate a strong one with "
        'python -c "import secrets; print(secrets.token_hex(32))"'
    )

TOKEN_TTL_HOURS = 12
PAGE_SIZE = 10
LOW_STOCK_THRESHOLD = 5
LOW_STOCK_ALERTS_LIMIT = 10
LOGIN_MAX_ATTEMPTS = 5
LOGIN_LOCKOUT_SECONDS = 15 * 60

SORT_COLUMNS = {
    "id": "p.id",
    "brand": "b.name",
    "name": "p.name",
    "price": "p.price",
    "quantity": "p.quantity",
}

_failed_logins: dict = {}

app = FastAPI(title="Inventory Management API")

# The Vite dev server origin; extend for production deployments.
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://127.0.0.1:5173",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Prometheus metrics: GET /metrics (request counts, latency, in-progress).
Instrumentator().instrument(app).expose(app)

_bearer = HTTPBearer(auto_error=False)


def get_db() -> Iterator[psycopg.Connection]:
    """
    One PostgreSQL connection per request, closed on exit.
    """

    conn = psycopg.connect(get_connection_string())

    try:
        yield conn
    finally:
        conn.close()


# ---------------------------------------------------------------- schemas


class CredentialsIn(BaseModel):
    username: str = Field(min_length=1, max_length=80)
    password: str = Field(min_length=1)


class SetupIn(CredentialsIn):
    pass


class UserCreateIn(BaseModel):
    username: str = Field(min_length=1, max_length=80)
    password: str = Field(min_length=8)
    role: str = "user"


class UserPatchIn(BaseModel):
    role: str | None = None
    password: str | None = Field(default=None, min_length=8)


class PasswordChangeIn(BaseModel):
    current_password: str = Field(min_length=1)
    password: str = Field(min_length=8)


class PasswordResetIn(BaseModel):
    password: str = Field(min_length=8)


class BrandIn(BaseModel):
    name: str = Field(min_length=1, max_length=120)


class ProductIn(BaseModel):
    brand_id: int
    name: str = Field(min_length=1, max_length=200)
    price: float = Field(gt=0)
    quantity: int = Field(ge=0)
    reorder_point: int = Field(default=10, ge=0)
    lead_time_days: int = Field(default=7, ge=1)
    reason: str | None = Field(default=None, max_length=200)


# ---------------------------------------------------------------- helpers


def create_token(user_id: int, username: str) -> str:
    payload = {
        "sub": str(user_id),
        "username": username,
        "exp": datetime.now(UTC) + timedelta(hours=TOKEN_TTL_HOURS),
    }
    return jwt.encode(payload, SECRET_KEY, algorithm="HS256")  # type: ignore[arg-type]  # SECRET_KEY validated at startup


def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(_bearer),
    db: psycopg.Connection = Depends(get_db),
) -> dict:
    """
    Resolve the bearer token to a live account. Tokens of deleted
    accounts are rejected here (ghost-session equivalent).
    """

    if credentials is None:
        raise HTTPException(status_code=401, detail="Not authenticated.")

    try:
        payload = jwt.decode(credentials.credentials, SECRET_KEY, algorithms=["HS256"])  # type: ignore[arg-type]  # SECRET_KEY validated at startup
    except jwt.PyJWTError:
        raise HTTPException(status_code=401, detail="Invalid or expired token.")

    user_id = int(payload.get("sub", 0))

    row = db.execute(
        "SELECT id, username, role FROM users WHERE id = %s",
        (user_id,),
    ).fetchone()

    if row is None:
        raise HTTPException(status_code=401, detail="Account no longer exists.")

    return {"id": row[0], "username": row[1], "role": row[2]}


def require_admin(user: dict = Depends(get_current_user)) -> dict:
    if user["role"] != "admin":
        raise HTTPException(status_code=403, detail="Admin only.")
    return user


def _register_failed_login(username: str) -> None:
    now = time.monotonic()
    count, first_ts = _failed_logins.get(username, (0, now))

    if now - first_ts > LOGIN_LOCKOUT_SECONDS:
        count, first_ts = 0, now

    _failed_logins[username] = (count + 1, first_ts)


def _login_is_locked(username: str) -> bool:
    entry = _failed_logins.get(username)

    if entry is None:
        return False

    count, first_ts = entry

    if time.monotonic() - first_ts > LOGIN_LOCKOUT_SECONDS:
        _failed_logins.pop(username, None)
        return False

    return count >= LOGIN_MAX_ATTEMPTS


def _clear_failed_logins(username: str) -> None:
    _failed_logins.pop(username, None)


def _user_count(db: psycopg.Connection) -> int:
    return db.execute("SELECT COUNT(*) FROM users").fetchone()[0]  # type: ignore[index]  # single-row query by construction


# ---------------------------------------------------------------- auth


@app.get("/api/auth/status")
def auth_status(db: psycopg.Connection = Depends(get_db)) -> dict:
    """
    Tells the SPA whether the first-run setup is still required.
    """

    return {"setup_required": _user_count(db) == 0}


@app.post("/api/auth/setup")
def setup(data: SetupIn, db: psycopg.Connection = Depends(get_db)) -> dict:
    """
    Create the initial admin. Only available while no user exists.
    """

    if _user_count(db) > 0:
        raise HTTPException(status_code=400, detail="Setup is already completed.")

    if len(data.password) < 8:
        raise HTTPException(status_code=400, detail="Password must be at least 8 characters.")

    if db.execute("SELECT 1 FROM users WHERE username = %s", (data.username,)).fetchone():
        raise HTTPException(status_code=400, detail="Username already taken.")

    row = db.execute(
        "INSERT INTO users (username, password_hash, role) VALUES (%s, %s, 'admin') RETURNING id",
        (data.username, generate_password_hash(data.password)),
    ).fetchone()
    db.commit()

    return {
        "access_token": create_token(row[0], data.username),  # type: ignore[index]  # single-row query by construction
        "token_type": "bearer",  # nosec B105  # token_type is the OAuth2 scheme, not a password
        "user": {"id": row[0], "username": data.username, "role": "admin"},  # type: ignore[index]  # single-row query by construction
    }


@app.post("/api/auth/login")
def login(data: CredentialsIn, db: psycopg.Connection = Depends(get_db)) -> dict:
    """
    Sign in with rate limiting: five failures per username lock
    it for 15 minutes; success clears the counter.
    """

    if _login_is_locked(data.username):
        raise HTTPException(
            status_code=429,
            detail="Too many failed attempts. Try again in 15 minutes.",
        )

    row = db.execute(
        "SELECT id, username, password_hash, role FROM users WHERE username = %s",
        (data.username,),
    ).fetchone()

    if row is None or not check_password_hash(row[2], data.password):
        _register_failed_login(data.username)
        raise HTTPException(status_code=401, detail="Invalid username or password.")

    _clear_failed_logins(data.username)

    return {
        "access_token": create_token(row[0], row[1]),
        "token_type": "bearer",  # nosec B105  # token_type is the OAuth2 scheme, not a password
        "user": {"id": row[0], "username": row[1], "role": row[3]},
    }


@app.get("/api/auth/me")
def me(user: dict = Depends(get_current_user)) -> dict:
    return user


@app.post("/api/auth/password")
def change_password(
    data: PasswordChangeIn,
    user: dict = Depends(get_current_user),
    db: psycopg.Connection = Depends(get_db),
) -> dict:
    """
    Self-service password change; requires the current password.
    """

    row = db.execute("SELECT password_hash FROM users WHERE id = %s", (user["id"],)).fetchone()

    if row is None:
        raise HTTPException(status_code=401, detail="Account no longer exists.")

    if not check_password_hash(row[0], data.current_password):
        raise HTTPException(status_code=400, detail="Current password is incorrect.")

    db.execute(
        "UPDATE users SET password_hash = %s WHERE id = %s",
        (generate_password_hash(data.password), user["id"]),
    )
    db.commit()

    return {"ok": True}


# ---------------------------------------------------------------- users


@app.get("/api/users")
def list_users(
    admin: dict = Depends(require_admin),
    db: psycopg.Connection = Depends(get_db),
) -> list:
    rows = db.execute("SELECT id, username, role FROM users ORDER BY id").fetchall()

    return [
        {"id": r[0], "username": r[1], "role": r[2], "is_you": r[0] == admin["id"]} for r in rows
    ]


@app.post("/api/users")
def create_user(
    data: UserCreateIn,
    admin: dict = Depends(require_admin),
    db: psycopg.Connection = Depends(get_db),
) -> dict:
    if data.role not in ("user", "admin"):
        raise HTTPException(status_code=400, detail="Role must be user or admin.")

    if db.execute("SELECT 1 FROM users WHERE username = %s", (data.username,)).fetchone():
        raise HTTPException(status_code=400, detail="Username already taken.")

    row = db.execute(
        "INSERT INTO users (username, password_hash, role) VALUES (%s, %s, %s) RETURNING id",
        (data.username, generate_password_hash(data.password), data.role),
    ).fetchone()
    db.commit()

    return {
        "id": row[0],  # type: ignore[index]  # single-row query by construction
        "username": data.username,
        "role": data.role,
        "is_you": False,
    }


@app.patch("/api/users/{user_id}")
def update_user(
    user_id: int,
    data: UserPatchIn,
    admin: dict = Depends(require_admin),
    db: psycopg.Connection = Depends(get_db),
) -> dict:
    row = db.execute("SELECT id, username, role FROM users WHERE id = %s", (user_id,)).fetchone()

    if row is None:
        raise HTTPException(status_code=404, detail="User not found.")

    new_role = data.role if data.role is not None else row[2]

    if new_role not in ("user", "admin"):
        raise HTTPException(status_code=400, detail="Role must be user or admin.")

    if row[2] == "admin" and new_role != "admin":
        admins = db.execute("SELECT COUNT(*) FROM users WHERE role = 'admin'").fetchone()[0]  # type: ignore[index]  # single-row query by construction

        if admins == 1:
            raise HTTPException(
                status_code=400,
                detail="The last remaining admin cannot be demoted.",
            )

    if data.password is not None:
        db.execute(
            "UPDATE users SET role = %s, password_hash = %s WHERE id = %s",
            (new_role, generate_password_hash(data.password), user_id),
        )
    else:
        db.execute("UPDATE users SET role = %s WHERE id = %s", (new_role, user_id))

    db.commit()

    return {
        "id": user_id,
        "username": row[1],
        "role": new_role,
        "is_you": user_id == admin["id"],
    }


@app.delete("/api/users/{user_id}")
def delete_user(
    user_id: int,
    admin: dict = Depends(require_admin),
    db: psycopg.Connection = Depends(get_db),
) -> dict:
    if user_id == admin["id"]:
        raise HTTPException(status_code=400, detail="You cannot delete yourself.")

    row = db.execute("SELECT role FROM users WHERE id = %s", (user_id,)).fetchone()

    if row is None:
        raise HTTPException(status_code=404, detail="User not found.")

    if row[0] == "admin":
        admins = db.execute("SELECT COUNT(*) FROM users WHERE role = 'admin'").fetchone()[0]  # type: ignore[index]  # single-row query by construction

        if admins == 1:
            raise HTTPException(
                status_code=400,
                detail="The last remaining admin cannot be deleted.",
            )

    db.execute("DELETE FROM users WHERE id = %s", (user_id,))
    db.commit()

    return {"ok": True}


@app.post("/api/users/{user_id}/password")
def reset_user_password(
    user_id: int,
    data: PasswordResetIn,
    admin: dict = Depends(require_admin),
    db: psycopg.Connection = Depends(get_db),
) -> dict:
    row = db.execute("SELECT id FROM users WHERE id = %s", (user_id,)).fetchone()

    if row is None:
        raise HTTPException(status_code=404, detail="User not found.")

    db.execute(
        "UPDATE users SET password_hash = %s WHERE id = %s",
        (generate_password_hash(data.password), user_id),
    )
    db.commit()

    return {"ok": True}


# ---------------------------------------------------------------- brands


@app.get("/api/brands")
def list_brands(
    user: dict = Depends(get_current_user),
    db: psycopg.Connection = Depends(get_db),
) -> list:
    rows = db.execute(
        "SELECT b.id, b.name, COUNT(p.id) AS product_count "
        "FROM brands b LEFT JOIN products p ON p.brand_id = b.id "
        "GROUP BY b.id, b.name ORDER BY b.name"
    ).fetchall()

    return [{"id": r[0], "name": r[1], "product_count": r[2]} for r in rows]


@app.post("/api/brands")
def create_brand(
    data: BrandIn,
    user: dict = Depends(get_current_user),
    db: psycopg.Connection = Depends(get_db),
) -> dict:
    if db.execute("SELECT 1 FROM brands WHERE LOWER(name) = LOWER(%s)", (data.name,)).fetchone():
        raise HTTPException(status_code=400, detail="This brand already exists.")

    row = db.execute("INSERT INTO brands (name) VALUES (%s) RETURNING id", (data.name,)).fetchone()
    db.commit()

    return {"id": row[0], "name": data.name, "product_count": 0}  # type: ignore[index]  # single-row query by construction


@app.patch("/api/brands/{brand_id}")
def update_brand(
    brand_id: int,
    data: BrandIn,
    user: dict = Depends(get_current_user),
    db: psycopg.Connection = Depends(get_db),
) -> dict:
    if db.execute("SELECT 1 FROM brands WHERE id = %s", (brand_id,)).fetchone() is None:
        raise HTTPException(status_code=404, detail="Brand not found.")

    if db.execute(
        "SELECT 1 FROM brands WHERE LOWER(name) = LOWER(%s) AND id != %s",
        (data.name, brand_id),
    ).fetchone():
        raise HTTPException(status_code=400, detail="This brand already exists.")

    db.execute("UPDATE brands SET name = %s WHERE id = %s", (data.name, brand_id))
    db.commit()

    return {"id": brand_id, "name": data.name}


@app.delete("/api/brands/{brand_id}")
def delete_brand(
    brand_id: int,
    user: dict = Depends(get_current_user),
    db: psycopg.Connection = Depends(get_db),
) -> dict:
    count = db.execute("SELECT COUNT(*) FROM products WHERE brand_id = %s", (brand_id,)).fetchone()[  # type: ignore[index]  # single-row query by construction
        0
    ]

    if count > 0:
        raise HTTPException(
            status_code=400,
            detail="This brand still has products and cannot be deleted.",
        )

    if db.execute("SELECT 1 FROM brands WHERE id = %s", (brand_id,)).fetchone() is None:
        raise HTTPException(status_code=404, detail="Brand not found.")

    db.execute("DELETE FROM brands WHERE id = %s", (brand_id,))
    db.commit()

    return {"ok": True}


# ---------------------------------------------------------------- products


def _escape_like(term: str) -> str:
    return term.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")


@app.get("/api/products")
def list_products(
    user: dict = Depends(get_current_user),
    db: psycopg.Connection = Depends(get_db),
    search: str = "",
    sort: str = "name",
    direction: str = "asc",
    page: int = Query(default=1, ge=1),
) -> dict:
    if sort not in SORT_COLUMNS:
        sort = "name"

    direction_sql = "DESC" if direction == "desc" else "ASC"
    order_by = f"{SORT_COLUMNS[sort]} {direction_sql}, p.id ASC"
    offset = (page - 1) * PAGE_SIZE
    like = f"%{_escape_like(search)}%"

    base = (
        "FROM products p JOIN brands b ON p.brand_id = b.id "
        "WHERE (%s = '' OR p.name ILIKE %s ESCAPE '\\' OR b.name ILIKE %s ESCAPE '\\')"
    )

    total = db.execute(f"SELECT COUNT(*) {base}", (search, like, like)).fetchone()[0]  # type: ignore[index]  # single-row query by construction

    rows = db.execute(
        f"SELECT p.id, p.brand_id, b.name, p.name, p.price, p.quantity "
        f"{base} ORDER BY {order_by} LIMIT %s OFFSET %s",
        (search, like, like, PAGE_SIZE, offset),
    ).fetchall()

    return {
        "items": [
            {
                "id": r[0],
                "brand_id": r[1],
                "brand": r[2],
                "name": r[3],
                "price": float(r[4]),
                "quantity": r[5],
            }
            for r in rows
        ],
        "page": page,
        "pages": max(1, (total + PAGE_SIZE - 1) // PAGE_SIZE),
        "total": total,
    }


def _record_stock_movement(
    conn: psycopg.Connection,
    product_id: int,
    delta: int,
    reason: str,
) -> None:
    """
    Append one stock_movements row for a real quantity change. Runs inside
    the caller's transaction: a failure before the commit rolls the whole
    product edit back with it (atomicity). qty keeps the sign of the delta
    (negative for 'out') — the signed-delta convention of stock_movements
    that the analytics pipeline sums directly.
    """

    conn.execute(
        "INSERT INTO stock_movements (product_id, in_out, qty, reason) "
        "VALUES (%s, %s, %s, %s)",
        (product_id, "in" if delta > 0 else "out", delta, reason),
    )


@app.post("/api/products")
def create_product(
    data: ProductIn,
    user: dict = Depends(get_current_user),
    db: psycopg.Connection = Depends(get_db),
) -> dict:
    brand = db.execute("SELECT name FROM brands WHERE id = %s", (data.brand_id,)).fetchone()

    if brand is None:
        raise HTTPException(status_code=400, detail="Selected brand does not exist.")

    row = db.execute(
        "INSERT INTO products (brand_id, name, price, quantity) "
        "VALUES (%s, %s, %s, %s) RETURNING id",
        (data.brand_id, data.name, Decimal(str(data.price)), data.quantity),
    ).fetchone()
    product_id = row[0]  # type: ignore[index]  # single-row query by construction

    # The initial stock level is itself a movement; a zero-qty creation
    # has nothing to record.
    if data.quantity > 0:
        _record_stock_movement(db, product_id, data.quantity, "initial")

    db.commit()

    return {
        "id": product_id,
        "brand_id": data.brand_id,
        "brand": brand[0],
        "name": data.name,
        "price": data.price,
        "quantity": data.quantity,
    }


@app.patch("/api/products/{product_id}")
def update_product(
    product_id: int,
    data: ProductIn,
    user: dict = Depends(get_current_user),
    db: psycopg.Connection = Depends(get_db),
) -> dict:
    current = db.execute(
        "SELECT quantity FROM products WHERE id = %s", (product_id,)
    ).fetchone()

    if current is None:
        raise HTTPException(status_code=404, detail="Product not found.")

    brand = db.execute("SELECT name FROM brands WHERE id = %s", (data.brand_id,)).fetchone()

    if brand is None:
        raise HTTPException(status_code=400, detail="Selected brand does not exist.")

    db.execute(
        "UPDATE products SET brand_id = %s, name = %s, price = %s, quantity = %s WHERE id = %s",
        (
            data.brand_id,
            data.name,
            Decimal(str(data.price)),
            data.quantity,
            product_id,
        ),
    )

    # Record the quantity change in the same transaction; no change in
    # quantity means no movement row.
    delta = data.quantity - (current[0] or 0)
    if delta != 0:
        _record_stock_movement(db, product_id, delta, data.reason or "manual_edit")

    db.commit()

    return {
        "id": product_id,
        "brand_id": data.brand_id,
        "brand": brand[0],
        "name": data.name,
        "price": data.price,
        "quantity": data.quantity,
    }


@app.delete("/api/products/{product_id}")
def delete_product(
    product_id: int,
    user: dict = Depends(get_current_user),
    db: psycopg.Connection = Depends(get_db),
) -> dict:
    if db.execute("SELECT 1 FROM products WHERE id = %s", (product_id,)).fetchone() is None:
        raise HTTPException(status_code=404, detail="Product not found.")

    # The movement history belongs to the product: the FK would block the
    # delete, so drop the rows in the same transaction (atomic).
    db.execute("DELETE FROM stock_movements WHERE product_id = %s", (product_id,))
    db.execute("DELETE FROM products WHERE id = %s", (product_id,))
    db.commit()

    return {"ok": True}


# ---------------------------------------------------------------- dashboard


@app.get("/api/dashboard/stats")
def dashboard_stats(
    user: dict = Depends(get_current_user),
    db: psycopg.Connection = Depends(get_db),
) -> dict:
    product_count = db.execute("SELECT COUNT(*) FROM products").fetchone()[0]  # type: ignore[index]  # single-row query by construction

    brand_count = db.execute("SELECT COUNT(*) FROM brands").fetchone()[0]  # type: ignore[index]  # single-row query by construction

    unit_count = db.execute("SELECT COALESCE(SUM(quantity), 0) FROM products").fetchone()[0]  # type: ignore[index]  # single-row query by construction

    total_value = db.execute("SELECT COALESCE(SUM(price * quantity), 0) FROM products").fetchone()[  # type: ignore[index]  # single-row query by construction
        0
    ]

    low_stock = db.execute(  # type: ignore[index]  # single-row query by construction
        "SELECT COUNT(*) FROM products WHERE quantity < %s",
        (LOW_STOCK_THRESHOLD,),
    ).fetchone()[0]

    low_stock_alerts = db.execute(  # type: ignore[index]  # single-row query by construction
        "SELECT id, name, quantity FROM products WHERE quantity < %s "
        "ORDER BY quantity ASC NULLS LAST, name ASC LIMIT %s",
        (LOW_STOCK_THRESHOLD, LOW_STOCK_ALERTS_LIMIT),
    ).fetchall()

    return {
        "products": product_count,
        "brands": brand_count,
        "units_in_stock": int(unit_count),
        "inventory_value": float(total_value),
        "low_stock": low_stock,
        "low_stock_threshold": LOW_STOCK_THRESHOLD,
        "low_stock_alerts": [
            {"product_id": r[0], "name": r[1], "remaining_qty": r[2] or 0}
            for r in low_stock_alerts
        ],
    }


# ---------------------------------------------------------------- csv import (P9)

IMPORT_MAX_BYTES = 1_000_000
IMPORT_MAX_ROWS = 1000
IMPORT_COLUMNS = ("name", "brand", "price", "quantity")


@app.post("/api/products/import")
def import_products_csv(
    file: UploadFile = File(...),
    user: dict = Depends(get_current_user),
    db: psycopg.Connection = Depends(get_db),
) -> dict:
    """
    Bulk-create products from a CSV file (utf-8, BOM tolerated). Columns
    are matched by header name; unknown brands and broken rows land in
    `errors`, existing (brand, name) pairs in `skipped`. Data rows are
    numbered from 1 after the header. Initial stock is recorded as an
    'import' movement (P8) — everything in one transaction.
    """

    if not (file.filename or "").lower().endswith(".csv"):
        raise HTTPException(status_code=400, detail="Only .csv files are accepted.")

    payload = file.file.read(IMPORT_MAX_BYTES + 1)
    if len(payload) > IMPORT_MAX_BYTES:
        raise HTTPException(status_code=400, detail="File exceeds the 1 MB limit.")

    rows = list(csv.reader(io.StringIO(payload.decode("utf-8-sig", errors="replace"))))
    if not rows:
        raise HTTPException(status_code=400, detail="File is empty.")

    header = [cell.strip().lower() for cell in rows[0]]
    missing = [column for column in IMPORT_COLUMNS if column not in header]
    if missing:
        raise HTTPException(
            status_code=400,
            detail=f"Missing required column(s): {', '.join(missing)}.",
        )
    column_index = {column: header.index(column) for column in IMPORT_COLUMNS}

    data_rows = [row for row in rows[1:] if any(cell.strip() for cell in row)]
    if not data_rows:
        raise HTTPException(status_code=400, detail="File has no data rows.")
    if len(data_rows) > IMPORT_MAX_ROWS:
        raise HTTPException(
            status_code=400,
            detail=f"Too many rows: {len(data_rows)} (max {IMPORT_MAX_ROWS}).",
        )

    brand_ids: dict[str, int | None] = {}

    def _lookup_brand_id(name: str) -> int | None:
        key = name.lower()
        if key not in brand_ids:
            row = db.execute(
                "SELECT id FROM brands WHERE lower(name) = %s ORDER BY id LIMIT 1",
                (key,),
            ).fetchone()
            brand_ids[key] = row[0] if row is not None else None  # type: ignore[index]  # single-row query by construction
        return brand_ids[key]

    existing_pairs = {
        (brand_id, name.lower())
        for brand_id, name in db.execute("SELECT brand_id, name FROM products").fetchall()
    }
    seen_in_file: set[tuple[int, str]] = set()
    imported = 0
    skipped: list[dict] = []
    errors: list[dict] = []
    valid_rows: list[tuple[int, int, str, Decimal, int]] = []

    for row_no, row in enumerate(data_rows, start=1):
        try:
            name = row[column_index["name"]].strip()
            brand_name = row[column_index["brand"]].strip()
        except IndexError:
            errors.append({"row": row_no, "reason": "missing value(s)"})
            continue

        try:
            price = Decimal(row[column_index["price"]].strip())
        except (IndexError, InvalidOperation):
            errors.append({"row": row_no, "reason": "invalid price"})
            continue

        try:
            quantity = int(row[column_index["quantity"]].strip())
        except (IndexError, ValueError):
            errors.append({"row": row_no, "reason": "invalid quantity"})
            continue

        if not name or len(name) > 200:
            errors.append({"row": row_no, "reason": "invalid name"})
            continue
        if not price.is_finite() or price <= 0:
            errors.append({"row": row_no, "reason": "invalid price"})
            continue
        if quantity < 0:
            errors.append({"row": row_no, "reason": "invalid quantity"})
            continue

        brand_id = _lookup_brand_id(brand_name)
        if brand_id is None:
            errors.append({"row": row_no, "reason": f"unknown brand: {brand_name}"})
            continue

        pair = (brand_id, name.lower())
        if pair in existing_pairs or pair in seen_in_file:
            skipped.append({"row": row_no, "reason": "duplicate"})
            continue

        seen_in_file.add(pair)
        valid_rows.append((row_no, brand_id, name, price, quantity))

    for _row_no, brand_id, name, price, quantity in valid_rows:
        product_id = db.execute(
            "INSERT INTO products (brand_id, name, price, quantity) "
            "VALUES (%s, %s, %s, %s) RETURNING id",
            (brand_id, name, price, quantity),
        ).fetchone()[0]  # type: ignore[index]  # single-row query by construction
        if quantity > 0:
            _record_stock_movement(db, product_id, quantity, "import")
        imported += 1

    db.commit()

    return {"imported": imported, "skipped": skipped, "errors": errors}


@app.get("/api/export/products.csv")
def export_products_csv(
    user: dict = Depends(get_current_user),
    db: psycopg.Connection = Depends(get_db),
) -> StreamingResponse:
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["ID", "Brand", "Name", "Price", "Quantity"])

    rows = db.execute(
        "SELECT p.id, b.name, p.name, p.price, p.quantity "
        "FROM products p JOIN brands b ON p.brand_id = b.id "
        "ORDER BY b.name, p.name, p.id"
    ).fetchall()

    for r in rows:
        writer.writerow([r[0], r[1], r[2], r[3], r[4]])

    output.seek(0)

    return StreamingResponse(
        iter([output.getvalue()]),
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=products.csv"},
    )


# ---------------------------------------------------------------- analytics (P7 — paginated, batched, OpenRouter fixed)

ANALYTICS_WINDOW_DAYS = 30
ANALYTICS_LEAD_DAYS = 14
DEFAULT_PAGE_SIZE = 10
MAX_PAGE_SIZE = 100
OPENROUTER_TIMEOUT = 15

OPENROUTER_BASE_URL = "https://openrouter.ai/api/v1/chat/completions"


def _linreg_slope(xs: list, ys: list) -> float:
    n = len(xs)
    if n < 2:
        return 0.0
    sx = sum(xs)
    sy = sum(ys)
    sxx = sum(x * x for x in xs)
    sxy = sum(x * y for x, y in zip(xs, ys))
    denom = n * sxx - sx * sx
    if denom == 0:
        return 0.0
    return (n * sxy - sx * sy) / denom


def _daily_series(movements: list) -> float | None:
    # movements = [(timestamp, qty_delta)]
    by_day: dict = {}
    for ts, qty in movements:
        d = ts.date() if hasattr(ts, "date") else ts
        by_day[d] = by_day.get(d, 0) + qty
    days = sorted(by_day)
    if len(days) < 2:
        return None
    first = days[0]
    cum = 0
    xs = []
    ys = []
    for d in days:
        cum += by_day[d]
        xs.append((d - first).days)
        ys.append(cum)
    if len(set(xs)) < 2:
        return None
    return _linreg_slope(xs, ys)


def _load_movements(db: psycopg.Connection) -> dict[int, list]:
    rows = db.execute(
        "SELECT product_id, timestamp, qty FROM stock_movements "
        "WHERE timestamp >= now() - interval '1 day' * %s ORDER BY timestamp ASC",
        (ANALYTICS_WINDOW_DAYS,),
    ).fetchall()
    series: dict[int, list] = {}
    for pid, ts, qty in rows:
        series.setdefault(pid, []).append((ts, qty))
    return series


def _forecast_for_product(movements: list, current_qty: int, reorder_point: int = 10, lead_time_days: int = 7) -> dict:
    slope = _daily_series(movements)
    if slope is None and movements:
        first_ts = movements[0][0]
        last_ts = movements[-1][0]
        span = max(1, (last_ts - first_ts).days if hasattr(last_ts, "days") else 1)
        total_qty = sum(q for _, q in movements)
        slope = total_qty / span
    if slope is None:
        slope = 0.0
    daily_rate = slope  # net per day; negative = depletion
    if daily_rate < 0 and current_qty > 0:
        days_until = max(1, int(current_qty / abs(daily_rate) + 0.5))
    else:
        days_until = None  # no consumption trend
    # Recommended restock = enough for lead-time + 10% safety, at least to threshold
    needed = 0
    if daily_rate < 0:
        needed = abs(daily_rate) * lead_time_days * 1.1
    target = max(current_qty + needed, reorder_point)
    recommended = max(0, round(target - current_qty))
    return {
        "days_until_stockout": days_until,
        "recommended_restock_qty": recommended,
        "daily_net_rate": round(daily_rate, 3),
    }


@app.get("/api/movements")
def movements(
    user: dict = Depends(get_current_user),
    db: psycopg.Connection = Depends(get_db),
    limit: int = Query(DEFAULT_PAGE_SIZE, ge=1, le=MAX_PAGE_SIZE),
    offset: int = Query(0, ge=0),
) -> dict:
    total_row = db.execute("SELECT COUNT(*) FROM stock_movements").fetchone()
    total = total_row[0] if total_row else 0
    rows = db.execute(
        "SELECT m.id, m.product_id, p.name, m.in_out, m.qty, m.reason, m.timestamp "
        "FROM stock_movements m JOIN products p ON p.id = m.product_id "
        "ORDER BY m.timestamp DESC LIMIT %s OFFSET %s",
        (limit, offset),
    ).fetchall()
    items = [
        {
            "movement_id": r[0],
            "product_id": r[1],
            "product_name": r[2],
            "in_out": r[3],
            "qty_delta": r[4],
            "reason": r[5] or "",
            "timestamp": r[6].isoformat() if hasattr(r[6], "isoformat") else str(r[6]),
        }
        for r in rows
    ]
    return {"items": items, "total": total}


def _extract_json_array(content: str) -> str:
    """
    Free-pool reasoning models often prepend Chain-of-Thought prose or a
    markdown fence to the JSON payload. Recover the outermost JSON array
    tolerantly: strip, drop ``` fences, else slice from the first '[' to
    the last ']'. Empty string means "no array found".
    """

    content = content.strip()
    if content.startswith("```"):
        first_newline = content.find("\n")
        content = content[first_newline + 1 :] if first_newline != -1 else ""
        content = content.strip()
        if content.endswith("```"):
            content = content[:-3].strip()
    if content and not content.startswith("["):
        start = content.find("[")
        end = content.rfind("]")
        content = content[start : end + 1] if start != -1 and end > start else ""
    return content


def _refine_forecasts_with_openrouter(forecasts: list) -> None:
    """
    Best-effort OpenRouter refinement. Only the current page (the most
    urgent slice) is sent, never the full catalog. No key → skip with a
    log line; any failure → keep the regression numbers (fallback).
    """

    if not forecasts:
        return

    api_key = os.getenv("OPENROUTER_API_KEY", "")
    if not api_key:
        print("openrouter: skip, OPENROUTER_API_KEY not set")
        return

    model = os.getenv("OPENROUTER_MODEL") or "openrouter/free"
    payload = [
        {
            "product_id": f["product_id"],
            "name": f["name"],
            "current_qty": f["current_qty"],
            "days_until_stockout": f["days_until_stockout"],
            "recommended_restock_qty": f["recommended_restock_qty"],
        }
        for f in forecasts
    ]
    print(f"openrouter: refining {len(payload)} items (model={model})")

    try:
        body = json.dumps({
            "model": model,
            "messages": [
                {
                    "role": "system",
                    "content": (
                        "You are an inventory forecasting assistant. Given a JSON "
                        "array of regression-based inventory forecasts (key fields: "
                        "product_id, name, current_qty, days_until_stockout, "
                        "recommended_restock_qty), refine predictions when sensible "
                        "and output ONLY the same array with updated values and "
                        "ai_refined=true. Keep values realistic; never invent new fields."
                    ),
                },
                {"role": "user", "content": f"Refine these forecasts\n{json.dumps(payload)}"},
            ],
            "max_tokens": 4000,
            "temperature": 0.2,
        })
        req = urllib.request.Request(
            OPENROUTER_BASE_URL,
            data=body.encode(),
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
            },
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=OPENROUTER_TIMEOUT) as resp:
            text = resp.read().decode()
        result = json.loads(text)
        content = result.get("choices", [{}])[0].get("message", {}).get("content", "")
        content = _extract_json_array(content)
        refined = json.loads(content) if content else None
        if not isinstance(refined, list):
            print("openrouter: failed: response was not a JSON array — regression fallback")
            return
        by_pid = {
            item["product_id"]: item
            for item in refined
            if isinstance(item, dict) and "product_id" in item
        }
        matched = 0
        for f in forecasts:
            item = by_pid.get(f["product_id"])
            if item is None:
                continue
            if "days_until_stockout" in item:
                f["days_until_stockout"] = item["days_until_stockout"]
            if "recommended_restock_qty" in item:
                f["recommended_restock_qty"] = item["recommended_restock_qty"]
            f["ai_refined"] = True
            matched += 1
        print(f"openrouter: ok, refined {matched}")
    except Exception as exc:
        print(f"openrouter: failed: {exc} — regression fallback")


@app.get("/api/forecast")
def forecast(
    user: dict = Depends(get_current_user),
    db: psycopg.Connection = Depends(get_db),
    limit: int = Query(DEFAULT_PAGE_SIZE, ge=1, le=MAX_PAGE_SIZE),
    offset: int = Query(0, ge=0),
) -> dict:
    rows = db.execute(
        "SELECT id, name, quantity, reorder_point, lead_time_days FROM products ORDER BY id"
    ).fetchall()
    series = _load_movements(db)
    forecasts = []
    for pid, name, qty, rp, lt in rows:
        res = _forecast_for_product(series.get(pid, []), qty or 0, reorder_point=rp, lead_time_days=lt)
        forecasts.append({
            "product_id": pid,
            "name": name,
            "current_qty": qty or 0,
            "days_until_stockout": res["days_until_stockout"],
            "recommended_restock_qty": res["recommended_restock_qty"],
            "daily_consumption_rate": round(max(0, -res["daily_net_rate"]), 3),
            "daily_net_rate": res["daily_net_rate"],
            "ai_refined": False,
        })
    # Most urgent first: days until stockout ASC; no-consumption items last.
    forecasts.sort(
        key=lambda f: (
            f["days_until_stockout"] is None,
            f["days_until_stockout"] or 0,
            f["product_id"],
        )
    )
    total = len(forecasts)
    page = forecasts[offset : offset + limit]
    # Refine only the current page (the top urgent slice), never the catalog.
    _refine_forecasts_with_openrouter(page)
    return {"forecasts": page, "total": total}


@app.get("/api/recommendations")
def recommendations(
    user: dict = Depends(get_current_user),
    db: psycopg.Connection = Depends(get_db),
    limit: int = Query(DEFAULT_PAGE_SIZE, ge=1, le=MAX_PAGE_SIZE),
    offset: int = Query(0, ge=0),
) -> dict:
    """
    Restock candidates from current quantities + recent movement trends:
    stock below LOW_STOCK_THRESHOLD, or depletion expected inside the
    lead-time window.
    """
    rows = db.execute(
        "SELECT id, name, quantity, reorder_point, lead_time_days FROM products ORDER BY id"
    ).fetchall()
    series = _load_movements(db)
    items = []
    for pid, name, qty, rp, lt in rows:
        res = _forecast_for_product(series.get(pid, []), qty or 0, reorder_point=rp, lead_time_days=lt)
        days = res["days_until_stockout"]
        needs_restock = (qty is not None and qty < rp) or (days is not None and days < lt)
        if needs_restock:
            items.append({
                "product_id": pid,
                "name": name,
                "current_qty": qty or 0,
                "recommended_qty": res["recommended_restock_qty"],
                "estimated_days_until_empty": days,
            })
    # Most urgent first: estimated days ASC; unknown depletion last.
    items.sort(
        key=lambda x: (
            x["estimated_days_until_empty"] is None,
            x["estimated_days_until_empty"] or 0,
            x["product_id"],
        )
    )
    return {"recommendations": items[offset : offset + limit], "total": len(items)}


@app.get("/api/health")
def health() -> dict:
    """Liveness: the process is up. No database access."""
    return {"status": "ok"}


@app.get("/api/ready")
def ready(db: psycopg.Connection = Depends(get_db)) -> dict:
    """Readiness: the database must answer a trivial query (503 otherwise)."""
    try:
        db.execute("SELECT 1").fetchone()
    except psycopg.Error:
        raise HTTPException(status_code=503, detail="Database unavailable")
    return {"status": "ready", "database": "up"}


# ---------------------------------------------------------------- SPA


# Serve the built React app (frontend/dist) from this same origin so the
# production-style deployment is a single process on one port. Registered
# after every /api route, so the JSON API keeps precedence. If the dist
# folder is absent (dev without a frontend build), the API works as before.
_FRONTEND_DIST = Path(__file__).resolve().parent / "frontend" / "dist"

if _FRONTEND_DIST.is_dir():
    if (_FRONTEND_DIST / "assets").is_dir():
        app.mount(
            "/assets",
            StaticFiles(directory=_FRONTEND_DIST / "assets"),
            name="spa-assets",
        )

    @app.get("/{spa_path:path}", include_in_schema=False)
    def spa(spa_path: str) -> FileResponse:
        """
        Serve a real file from dist, or fall back to index.html so
        client-side routes like /login resolve on hard refresh.
        """

        candidate = (_FRONTEND_DIST / spa_path).resolve()

        if spa_path and str(candidate).startswith(str(_FRONTEND_DIST)) and candidate.is_file():
            return FileResponse(candidate)

        return FileResponse(_FRONTEND_DIST / "index.html")


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="127.0.0.1", port=8000)
