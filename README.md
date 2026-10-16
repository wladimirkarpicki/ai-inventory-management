# Inventory Management System

[![Tests](https://github.com/wladimirkarpicki/inventory-management-system/actions/workflows/tests.yml/badge.svg)](https://github.com/wladimirkarpicki/inventory-management-system/actions/workflows/tests.yml)

A web-based inventory management application built with Python, Flask, and PostgreSQL.

## Features

- User authentication — all pages require sign-in, with a first-run setup for the initial admin account
- Admin-only user management: create users, change roles, delete accounts — with server-side safety rules
- Dashboard with live inventory statistics
- View, search, and sort products; CSV export of the inventory
- Add, edit, and delete products (brand, name, price, quantity)
- Manage brands: add, edit, and delete — brands that still have products cannot be deleted
- Two-step selection flows for editing and deleting (brand → product → form)
- Server-side form validation with friendly error messages
- Friendly error page when the database is unavailable
- One PostgreSQL connection per request
- Automated test suite (pytest) with continuous integration on GitHub Actions
- CSRF protection on all forms, login rate limiting, and session invalidation for deleted accounts

## Technologies

- Python 3
- Flask
- PostgreSQL
- psycopg 3
- Jinja2
- python-dotenv

## Installation

1. Clone the repository:

```bash
git clone https://github.com/wladimirkarpicki/inventory-management-system.git
cd inventory-management-system
```

2. Install dependencies:

```bash
pip install -r requirements.txt
```

For development and testing, also install the dev dependencies:

```bash
pip install -r requirements-dev.txt
```

3. Create a `.env` file in the project root:

```env
DATABASE_HOST=localhost
DATABASE_NAME=your_database
DATABASE_USER=your_username
DATABASE_PASSWORD=your_password
SECRET_KEY=your_secret_key
```

`SECRET_KEY` signs the session cookies and is required — generate one with:

```bash
python -c "import secrets; print(secrets.token_hex(32))"
```

Optionally add `FLASK_DEBUG=1` to enable Flask debug mode and auto-reload during development. Debug mode is off by default.

4. Create the database tables:

```bash
psql -d your_database -f schema.sql
```

## Run

```bash
python app.py
```

Then open http://127.0.0.1:5000 in your browser.

## First Run

On first launch the app has no users yet, so every page redirects to **/setup**. Create the initial account there — it becomes the **admin**. The setup page closes itself afterwards, and everyone must sign in at **/login**.

## User Management

The admin can manage accounts from the **Users** page (visible in the navigation only for admins):

- **Create** users with a username, a password of at least 8 characters, and a role — regular **User** or **Admin**.
- **Change roles** from each account's Edit page.
- **Reset passwords** from each account's Password page — the old password is not required.
- **Delete** accounts after a confirmation step.

Every signed-in user can change their own password via **Change Password** in the navigation; that flow always requires the current password, while the admin reset does not.

Two safety rules are enforced server-side: the last remaining admin cannot be demoted or deleted (so the installation can never lock itself out of administration), and you cannot delete the account you are currently signed in with. Regular users can work with products and brands but receive 403 on all account management pages.

## Security

- **CSRF protection** — every form carries a per-session token; a POST request without a valid token is rejected with 400 before it reaches any route.
- **Login rate limiting** — five failed sign-in attempts for the same username lock that username for 15 minutes; a successful sign-in resets the counter. The attempt state is kept in process memory, so it also resets when the server restarts.
- **Session invalidation** — a session whose account no longer exists (for example, deleted by an admin) stops working on the very next request.
- Passwords are stored as salted werkzeug hashes, all SQL statements are parameterized, search terms escape LIKE wildcards, and role checks for admin pages run server-side in the request guard.
- **Cookie flags** — the session cookie is `HttpOnly` with `SameSite=Lax` (defense-in-depth alongside the CSRF token); the `Secure` flag is opt-in via `SESSION_COOKIE_SECURE=1` for HTTPS deployments.
- **Security headers** — every response carries `X-Content-Type-Options: nosniff`, `X-Frame-Options: DENY`, `Referrer-Policy: no-referrer`, and a restrictive Content-Security-Policy (`default-src 'self'; style-src 'self' 'unsafe-inline'`).
- **Secret key strength** — `SECRET_KEY` must be at least 32 characters at startup.
- Full audit: **[SECURITY.md](SECURITY.md)**.

## Testing

The test suite runs the whole application against a throwaway PostgreSQL database created from `schema.sql` — the database configured in `.env` is never touched.

```bash
pip install -r requirements-dev.txt
python -m pytest
```

It covers authentication and the first-run setup flow, user management with all of its safety rules, product and brand CRUD with validation, search (including LIKE-wildcard escaping), sorting, pagination, CSV export, and the dashboard statistics. Every test starts from a clean database, so tests can run in any order.

GitHub Actions runs the same suite on every push — see `.github/workflows/tests.yml`.

## Project Structure

- `app.py` — Flask application with all routes
- `database.py` — reads `.env` and builds the PostgreSQL connection string
- `schema.sql` — database schema for a fresh installation
- `templates/` — Jinja2 templates
- `tests/` — pytest test suite
- `requirements.txt` — runtime dependencies
- `requirements-dev.txt` — development dependencies (pytest)
- `pytest.ini` — pytest configuration
- `.github/workflows/tests.yml` — CI pipeline
