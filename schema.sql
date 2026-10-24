-- Inventory Management System - database schema
--
-- Usage:
--   psql -d <database> -f schema.sql
--
-- Safe to re-run: existing tables are left untouched.

CREATE TABLE IF NOT EXISTS brands (
    id SERIAL PRIMARY KEY,
    name VARCHAR(100) NOT NULL UNIQUE
);

CREATE TABLE IF NOT EXISTS products (
    id SERIAL PRIMARY KEY,
    name VARCHAR NOT NULL,
    brand_id INTEGER NOT NULL REFERENCES brands (id),
    price NUMERIC NOT NULL,
    quantity INTEGER,
    reorder_point INTEGER NOT NULL DEFAULT 10,
    lead_time_days INTEGER NOT NULL DEFAULT 7
);

-- One product per (brand, case-insensitive name) — the same rule the
-- CSV import deduplicates by, enforced by the database (P18).
CREATE UNIQUE INDEX IF NOT EXISTS idx_products_brand_lower_name
    ON products (brand_id, LOWER(name));

CREATE TABLE IF NOT EXISTS users (
    id SERIAL PRIMARY KEY,
    username VARCHAR(100) NOT NULL UNIQUE,
    password_hash VARCHAR(255) NOT NULL,
    role VARCHAR(20) NOT NULL DEFAULT 'user'
);

CREATE TABLE IF NOT EXISTS stock_movements (
    id SERIAL PRIMARY KEY,
    product_id INTEGER NOT NULL REFERENCES products (id),
    in_out VARCHAR(10) NOT NULL CHECK (in_out IN ('in', 'out')),
    qty INTEGER NOT NULL DEFAULT 0,
    reason TEXT NOT NULL DEFAULT '',
    timestamp TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT now()
);
