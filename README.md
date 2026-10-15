# Inventory Management System

A web-based inventory management application built with Python, Flask, and PostgreSQL.

## Features

- View all products with pagination
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

## Project Structure

- `app.py` — Flask application with all routes
- `database.py` — reads `.env` and builds the PostgreSQL connection string
- `schema.sql` — database schema for a fresh installation
- `templates/` — Jinja2 templates
- `requirements.txt` — Python dependencies
