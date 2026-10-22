-- Migration: create stock_movements table
-- Run: psql -d inventory -f migrations/001_stock_movements.sql

CREATE TABLE IF NOT EXISTS stock_movements (
    id SERIAL PRIMARY KEY,
    product_id INTEGER NOT NULL REFERENCES products (id),
    in_out VARCHAR(10) NOT NULL CHECK (in_out IN ('in', 'out')),
    qty INTEGER NOT NULL DEFAULT 0,
    reason TEXT NOT NULL DEFAULT '',
    timestamp TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT now()
);

-- Index for fast queries
CREATE INDEX IF NOT EXISTS idx_stock_movements_product_id ON stock_movements (product_id);
CREATE INDEX IF NOT EXISTS idx_stock_movements_timestamp ON stock_movements (timestamp DESC);

COMMENT ON TABLE stock_movements IS 'Stock movement history: in/out qty delta and reason per product';
COMMENT ON COLUMN stock_movements.in_out IS 'in = stock increase, out = stock decrease';
COMMENT ON COLUMN stock_movements.qty IS 'Quantity delta (positive or negative depending on in_out)';
COMMENT ON COLUMN stock_movements.reason IS 'Free-text reason for the movement';
COMMENT ON COLUMN stock_movements.timestamp IS 'When the movement occurred';