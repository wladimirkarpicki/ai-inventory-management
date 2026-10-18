"""
Inventory Management System - FastAPI JSON API.

Replaces the Flask JSON layer for the React SPA. The signed-in
identity travels as a bearer token; every request re-checks the
account in the database, so tokens of deleted accounts stop
working immediately.
"""

import csv
import io
import os
import time
from collections.abc import Iterator
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from pathlib import Path

import jwt
import psycopg
from dotenv import load_dotenv
from fastapi import Depends, FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, StreamingResponse
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from fastapi.staticfiles import StaticFiles
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
    db.commit()

    return {
        "id": row[0],  # type: ignore[index]  # single-row query by construction
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
    if db.execute("SELECT 1 FROM products WHERE id = %s", (product_id,)).fetchone() is None:
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

    return {
        "products": product_count,
        "brands": brand_count,
        "units_in_stock": int(unit_count),
        "inventory_value": float(total_value),
        "low_stock": low_stock,
        "low_stock_threshold": LOW_STOCK_THRESHOLD,
    }


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


@app.get("/api/health")
def health() -> dict:
    return {"status": "ok"}


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
