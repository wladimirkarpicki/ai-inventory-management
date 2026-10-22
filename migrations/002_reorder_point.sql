-- Migration 002: reorder point + lead time days
-- P10: intelligent thresholds + restock calculation

ALTER TABLE products
  ADD COLUMN IF NOT EXISTS reorder_point INT NOT NULL DEFAULT 10,
  ADD COLUMN IF NOT EXISTS lead_time_days INT NOT NULL DEFAULT 7;

COMMENT ON COLUMN products.reorder_point IS 'Per-product low-stock threshold (default 10)';
COMMENT ON COLUMN products.lead_time_days IS 'Lead-time in days for restock calculation (default 7)';

-- Idempotent: repeat run has no effect (IF NOT EXISTS + COMMENT is a no-op re-set)
