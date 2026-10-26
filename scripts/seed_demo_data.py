"""Seed the local dev database with demo inventory data.

20 real brands, ~50 real products each, approximate USD prices, random stock 1-100.
Existing data is kept; brands are matched case-insensitively to avoid duplicates.

Usage (from the repo root):
    python scripts/seed_demo_data.py           # add demo data
    python scripts/seed_demo_data.py --force   # allow re-run
"""

import random
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import psycopg

from database import get_connection_string
from scripts.seed_data_part1 import BRANDS_PART1
from scripts.seed_data_part2 import BRANDS_PART2

MIN_PRODUCTS = 50


def main() -> None:
    force = "--force" in sys.argv
    rng = random.Random(20261018)

    all_brands = {**BRANDS_PART1, **BRANDS_PART2}
    for name, items in all_brands.items():
        if len(items) < MIN_PRODUCTS:
            raise SystemExit(
                f"brand {name!r} has {len(items)} products, need at least {MIN_PRODUCTS}"
            )

    with psycopg.connect(get_connection_string()) as conn:
        total = conn.execute("SELECT COUNT(*) FROM products").fetchone()[0]
        if total >= 1000 and not force:
            print(f"products table already has {total} rows; pass --force to seed anyway")
            return

        inserted = 0
        for brand_name, items in all_brands.items():
            row = conn.execute(
                "SELECT id FROM brands WHERE LOWER(name) = LOWER(%s)", (brand_name,)
            ).fetchone()
            if row is None:
                row = conn.execute(
                    "INSERT INTO brands (name) VALUES (%s) RETURNING id", (brand_name,)
                ).fetchone()
                print(f"+ brand {brand_name} (id={row[0]})")
            else:
                print(f"= brand {brand_name} exists (id={row[0]})")
            brand_id = row[0]
            for name, price in items:
                cur = conn.execute(
                    "INSERT INTO products (brand_id, name, price, quantity, "
                    "reorder_point, lead_time_days) "
                    "VALUES (%s, %s, %s, %s, %s, %s) "
                    "ON CONFLICT DO NOTHING",
                    (
                        brand_id,
                        name,
                        price,
                        rng.randint(1, 100),
                        rng.randint(5, 30),  # varied reorder points
                        rng.randint(3, 14),  # varied supplier lead times
                    ),
                )
                inserted += cur.rowcount
            print(f"  -> {len(items)} products for {brand_name}")
        conn.commit()

        brands_after = conn.execute("SELECT COUNT(*) FROM brands").fetchone()[0]
        products_after = conn.execute("SELECT COUNT(*) FROM products").fetchone()[0]
        print(
            f"Inserted {inserted} products. Totals: {brands_after} brands, {products_after} products."
        )


if __name__ == "__main__":
    main()
