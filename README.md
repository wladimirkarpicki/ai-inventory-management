# Inventory Management System

A web-based inventory management application built with Python, Flask, and PostgreSQL.

## Features

- User authentication — all pages require sign-in, with a first-run setup for the initial admin account
- Admin-only user management: create additional users (regular or admin) from the Users page
- Dashboard with live inventory statistics
- View, search, and sort products; CSV export of the inventory
- Add, edit, and delete products (brand, name, price, quantity)
- Manage brands: add, edit, and delete — brands that still have products cannot be deleted
- Two-step selection flows for editing and deleting (brand → product → form)
- Server-side form validation with friendly error messages
- Friendly error page when the database is unavailable
- One PostgreSQL connection per request

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
- **Delete** accounts after a confirmation step.

Two safety rules are enforced server-side: the last remaining admin cannot be demoted or deleted (so the installation can never lock itself out of administration), and you cannot delete the account you are currently signed in with. Regular users can work with products and brands but receive 403 on all account management pages.

## Project Structure

- `app.py` — Flask application with all routes
- `database.py` — reads `.env` and builds the PostgreSQL connection string
- `schema.sql` — database schema for a fresh installation
- `templates/` — Jinja2 templates
- `requirements.txt` — Python dependencies
