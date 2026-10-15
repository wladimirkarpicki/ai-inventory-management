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
