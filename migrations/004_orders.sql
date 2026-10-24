-- 004: purchase orders (P25).
--
-- An order restocks one product; the lifecycle is
-- ordered -> received | cancelled. Receiving an order adds the ordered
-- quantity to the product and records a matching 'purchase_order'
-- stock movement in the same transaction, so Recent movements,
-- Dynamics and the forecast update together. The expected arrival date
-- is derived from the product's supplier lead time at creation.
--
-- Idempotent: re-running is a no-op.

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