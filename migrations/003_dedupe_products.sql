-- 003: remove duplicate products and enforce uniqueness (P18).
--
-- Root cause: scripts/seed_demo_data.py ran twice, so every
-- (brand, name) pair exists twice. Loser rows (higher id in each
-- duplicate group) are deleted together with their stock movements —
-- the keeper keeps its own movement history, so analytics stay
-- consistent. The unique index turns the CSV-import duplicate rule
-- into a database guarantee.
--
-- Idempotent: re-running is a no-op.

-- 1) Drop movements that belong to duplicate (loser) product rows.
DELETE FROM stock_movements
WHERE product_id IN (
    SELECT id
    FROM (
        SELECT id,
               ROW_NUMBER() OVER (
                   PARTITION BY brand_id, LOWER(name)
                   ORDER BY id
               ) AS rn
        FROM products
    ) ranked
    WHERE ranked.rn > 1
);

-- 2) Drop the duplicate product rows themselves (first-seed copy stays).
DELETE FROM products
WHERE id IN (
    SELECT id
    FROM (
        SELECT id,
               ROW_NUMBER() OVER (
                   PARTITION BY brand_id, LOWER(name)
                   ORDER BY id
               ) AS rn
        FROM products
    ) ranked
    WHERE ranked.rn > 1
);

-- 3) One product per (brand, case-insensitive name) from now on.
CREATE UNIQUE INDEX IF NOT EXISTS idx_products_brand_lower_name
    ON products (brand_id, LOWER(name));
