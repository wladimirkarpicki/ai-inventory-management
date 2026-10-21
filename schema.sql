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
    quantity INTEGER
);

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
