-- Migration 005: per-product minimum quantity (inventory health)
--
-- Adds the per-product minimum stock level that drives the stock-status
-- classification (OUT OF STOCK / LOW STOCK / IN STOCK) and the
-- recommended replenishment quantity (max(0, min_quantity - quantity)).
--
-- Existing rows are backfilled with the DEFAULT 5 applied by ADD COLUMN,
-- so no separate UPDATE is needed. The CHECK keeps the value
-- non-negative at the database level, mirroring the API schema
-- constraint (Field(ge=0)).
--
-- Idempotent: repeat run has no effect (IF NOT EXISTS + named constraint).
--
-- Scope: this migration is for databases created from a schema BEFORE the
-- column existed. A database created from the current schema.sql already
-- has both the column and its CHECK, so running this against one is a
-- no-op apart from one redundant second CHECK, which is harmless. Note
-- also that ADD COLUMN IF NOT EXISTS validates nothing about a column
-- that already exists, so it cannot repair a wrong definition.

ALTER TABLE products
  ADD COLUMN IF NOT EXISTS min_quantity INTEGER NOT NULL DEFAULT 5;

-- Named constraint so re-runs are no-ops (an unnamed CHECK would raise on
-- a second run).
ALTER TABLE products
  DROP CONSTRAINT IF EXISTS products_min_quantity_non_negative;

ALTER TABLE products
  ADD CONSTRAINT products_min_quantity_non_negative CHECK (min_quantity >= 0);

COMMENT ON COLUMN products.min_quantity IS 'Per-product minimum stock level (default 5, never negative)';
