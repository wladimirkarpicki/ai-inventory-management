# Inventory Management System

[![Tests](https://github.com/wladimirkarpicki/inventory-management-system/actions/workflows/tests.yml/badge.svg)](https://github.com/wladimirkarpicki/inventory-management-system/actions/workflows/tests.yml)
[![Security](https://github.com/wladimirkarpicki/inventory-management-system/actions/workflows/security.yml/badge.svg)](https://github.com/wladimirkarpicki/inventory-management-system/actions/workflows/security.yml)

A web-based inventory management application built with Python, FastAPI, PostgreSQL, and a React SPA frontend — with AI-powered demand forecasting, purchase-order management, and movement analytics.

## Features

### Core inventory
- User authentication — all pages require sign-in, with a first-run setup for the initial admin account
- Admin-only user management: create users, change roles, reset passwords, delete accounts — with server-side safety rules
- View, search, sort, and filter products; CSV export of the inventory
- Add, edit, and delete products — with per-product **reorder point** and **supplier lead time**
- One product per (brand, case-insensitive name) — enforced at the database level
- Manage brands: add, edit, and delete — brands that still have products cannot be deleted
- Quick filter: **"Below reorder point"** shows only items whose stock has dipped under their threshold
- Clickable sortable column headers (direction arrows, per-column toggling)
- CSV bulk import with dedup, validation, and per-row error reporting
- Server-side validation with friendly error messages; friendly error page when the database is unavailable
- Login rate limiting, token invalidation for deleted accounts, and last-admin / self-delete protection

### Smart forecasting & recommendations
- **Linear-regression demand forecast** per product over a 30-day window — days until stockout and recommended restock quantity
- **AI refinement** (optional): rows refined by an LLM carry an `AI` badge; every failure falls back to the regression values, so the forecast never depends on the LLM being up
- Restock formula accounts for each product's lead time: `needed = daily sales rate × lead_time × 1.1` — with the reorder point as a floor
- **Recommendations** list the most urgent restock candidates — flagged with **open purchase orders** so the same item isn't ordered twice
- **Forecast cache** (10-minute TTL) — recomputes only on expiry or on any product write

### Purchase orders
- Full lifecycle: **ordered → received | cancelled** — with expected-arrival dates derived from each product's lead time
- Receiving an order adds the quantity to stock **and** records a matching `purchase_order` movement in the same transaction — Recent movements, Dynamics, and the forecast all update together
- One-click **Order** buttons from the Recommendations and Low-stock tabs
- Overdue orders highlighted in red (expected date in the past)
- New-order dialog with product typeahead

### Movement analytics
- Every real quantity change (create, edit, CSV import, order receipt) automatically writes a `stock_movements` row — signed quantities, single transaction
- **Dashboard tabs**: Forecast · Recommendations · Stock dynamics · Recent movements · Low stock · Orders
- **Stock dynamics**: in/out bar chart with a 7-day rolling-average consumption line; **Top movers** leaderboards (biggest restocks / biggest consumption); **Daily detail** table with per-day net and running cumulative balance; 30/90-day period switcher; KPI strip (units in/out, net, avg daily out, peak day, active days)
- **Low stock** tab: all below-threshold products, paginated, the most depleted first, with reorder point shown
- **CSV export** of the full movement history
- Paginated API for every list endpoint (limit/offset/total)

## Technologies

- Python 3.13 · FastAPI · PostgreSQL 16 · psycopg 3
- PyJWT (bearer tokens, 12-hour expiry) · Prometheus metrics
- React 19 · TypeScript · Vite · Tailwind CSS v4 · shadcn/ui · Recharts
- NVIDIA Build API (optional, for AI forecast refinement)

## Installation

1. Clone the repository:

```bash
git clone https://github.com/wladimirkarpicki/inventory-management-system.git
cd inventory-management-system
```

2. Install Python dependencies:

```bash
pip install -r requirements.txt
```

For development and testing, also install the dev dependencies:

```bash
pip install -r requirements-dev.txt
```

3. Install frontend dependencies:

```bash
cd frontend && pnpm install
cd ..
```

4. Create a `.env` file in the project root — copy `.env.template` as a starting point:

```env
DATABASE_HOST=localhost
DATABASE_NAME=your_database
DATABASE_USER=your_username
DATABASE_PASSWORD=your_password
SECRET_KEY=your_secret_key
```

`SECRET_KEY` signs the JWT tokens and is required — generate one with:

```bash
python -c "import secrets; print(secrets.token_hex(32))"
```

5. Create the database tables:

```bash
psql -d your_database -f schema.sql
```

6. Optional — seed demo data:

```bash
python -m scripts.seed_demo_data            # ~1000 products across 20 brands
python -m scripts.seed_movements --wipe     # 30 days of realistic movement history
```

## Run

Backend:

```bash
uvicorn main:app --port 8000
```

Frontend:

```bash
cd frontend && pnpm dev
```

Then open http://127.0.0.1:5173 in your browser.

The Vite dev server proxies `/api/*` to port 8000, so no CORS setup is needed beyond the dev origins already configured in `main.py`. For a production bundle run `pnpm build` in `frontend/`.

## Docker

The production stack (multi-stage image → non-root runtime, PostgreSQL 16) runs as one command:

```bash
docker compose up -d              # app on http://localhost:8000
```

- Both services carry healthchecks (`/api/ready` for the stack, DB-native for PostgreSQL), resource limits (0.5 CPU / 512 MB), `restart: unless-stopped` and log rotation.
- **Observability, opt-in**: `docker compose --profile monitoring up -d` adds Prometheus (scrapes `/metrics`) and Grafana on http://localhost:3000 with a provisioned datasource.
- **Dev image**: `Dockerfile.dev` runs `uvicorn --reload` with the dev dependencies installed.
- Health probes: `/api/health` = liveness, `/api/ready` = readiness with a DB probe, `/metrics` = Prometheus exposition.

See **[docs/OPERATIONS.md](docs/OPERATIONS.md)** for backups (`scripts/backup.sh`), restore, the monitoring stack and the full runbook.

## First Run

On first launch the app has no users yet, so every page redirects to **/setup**. Create the initial account there — it becomes the **admin**. The setup page closes itself afterwards, and everyone must sign in at **/login**.

## User Management

The admin can manage accounts from the **Users** page (visible in the navigation only for admins):

- **Create** users with a username, a password of at least 8 characters, and a role — regular **User** or **Admin**.
- **Change roles** for existing accounts.
- **Reset passwords** for any account — the old password is not required.
- **Delete** accounts after a confirmation step.

Every signed-in user can change their own password via **Change Password** in the navigation; that flow always requires the current password, while the admin reset does not.

Two safety rules are enforced server-side: the last remaining admin cannot be demoted or deleted (so the installation can never lock itself out of administration), and you cannot delete the account you are currently signed in with. Regular users can work with products, brands, and orders but receive 403 on all account management pages.

## Security

- **Login rate limiting** — five failed sign-in attempts for the same username lock that username for 15 minutes; a successful sign-in resets the counter. The attempt state is kept in process memory, so it also resets when the server restarts.
- **Token invalidation** — a token whose account no longer exists (for example, deleted by an admin) stops working on the very next request, because every request re-fetches the account from the database.
- Passwords are stored as salted bcrypt hashes, all SQL statements are parameterized, search terms escape LIKE wildcards, and role checks for admin pages run server-side in the request guard.
- **Security headers** — every response carries `X-Content-Type-Options: nosniff`, `X-Frame-Options: DENY`, `Referrer-Policy: no-referrer`, and a restrictive Content-Security-Policy (`default-src 'self'; style-src 'self' 'unsafe-inline'`).
- **Secret key strength** — `SECRET_KEY` must be at least 32 characters at startup.
- Full audit: **[SECURITY.md](SECURITY.md)**.

## Testing

The test suite runs the whole application against a throwaway PostgreSQL database created from `schema.sql` — the database configured in `.env` is never touched.

```bash
pip install -r requirements-dev.txt
python -m pytest
```

It covers authentication and the first-run setup flow, user management with all of its safety rules, product and brand CRUD with validation and uniqueness, search (including LIKE-wildcard escaping), sorting, pagination, the low-stock filter, CSV export and import, the dashboard statistics, movement analytics (daily aggregates, top movers, forecasts with cache/LLM fallback), purchase orders (create, list, receive, cancel, transitions), and the health/readiness/metrics endpoints. Every test starts from a clean database, so tests can run in any order.

```bash
python -m pytest --cov=. --cov-report=term     # coverage report (~90%)
cd frontend && pnpm exec vitest run            # SPA unit tests
```

GitHub Actions runs the whole pipeline — tests with coverage, frontend (typecheck + unit tests + build), docker image build, and the Security workflow (ruff, mypy, bandit, pip-audit) — on every push. See **[docs/CI.md](docs/CI.md)**.

The same Ruff rules run locally on every commit via pre-commit:

```bash
pip install pre-commit
pre-commit install
```

## Project Structure

- `main.py` — FastAPI JSON backend consumed by the SPA
- `database.py` — reads `.env` and builds the PostgreSQL connection string
- `schema.sql` — database schema for a fresh installation
- `migrations/` — incremental schema changes (002 reorder points, 003 dedup + unique index, 004 orders)
- `frontend/` — React 19 + TypeScript SPA (Vite, Tailwind CSS v4, shadcn/ui, Recharts)
- `tests/` — pytest test suite (FastAPI API, analytics, orders)
- `requirements.txt` — runtime dependencies
- `requirements-dev.txt` — development dependencies (pytest, coverage, linters)
- `pytest.ini` — pytest configuration
- `Dockerfile` / `Dockerfile.dev` — production and development images
- `compose.yml` — app + db stack, with an opt-in `monitoring` profile (Prometheus + Grafana)
- `monitoring/` — Prometheus scrape config and Grafana datasource provisioning
- `scripts/` — backup, health monitor, demo-data seeders
- `docs/` — [CI.md](docs/CI.md) (pipeline overview), [OPERATIONS.md](docs/OPERATIONS.md) (runbook)
- `.github/workflows/` — Tests and Security CI pipelines