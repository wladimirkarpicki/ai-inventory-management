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
    lead_time_days INTEGER NOT NULL DEFAULT 7,
    min_quantity INTEGER NOT NULL DEFAULT 5,
    CONSTRAINT products_min_quantity_non_negative CHECK (min_quantity >= 0)
);

-- Per-product minimum stock level (default 5). The inventory-health
-- classifier compares quantity against it: OUT OF STOCK (0), LOW STOCK
-- (0 < quantity < min_quantity), IN STOCK (quantity >= min_quantity).
COMMENT ON COLUMN products.min_quantity IS 'Per-product minimum stock level (default 5, never negative)';

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

-- Movement history indexes. Both are required: /api/movements filters by
-- product_id, and /api/movements/daily plus /api/movements/top filter and
-- ORDER BY on timestamp, so without these the analytics queries run
-- sequential scans. These match migrations/001_stock_movements.sql exactly
-- so a fresh volume and a migrated database end up with the same schema.
CREATE INDEX IF NOT EXISTS idx_stock_movements_product_id
    ON stock_movements (product_id);

CREATE INDEX IF NOT EXISTS idx_stock_movements_timestamp
    ON stock_movements (timestamp DESC);

-- Purchase orders (P25): ordered -> received | cancelled.
CREATE TABLE IF NOT EXISTS orders (
    id SERIAL PRIMARY KEY,
    product_id INTEGER NOT NULL REFERENCES products (id),
    qty INTEGER NOT NULL CHECK (qty > 0),
    status VARCHAR(20) NOT NULL DEFAULT 'ordered'
        CHECK (status IN ('ordered', 'received', 'cancelled')),
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT now(),
    expected_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT now(),
    received_at TIMESTAMP WITH TIME ZONE
);

CREATE INDEX IF NOT EXISTS idx_orders_status_created
    ON orders (status, created_at DESC);
