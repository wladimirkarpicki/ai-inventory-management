#!/usr/bin/env python3
"""
Seed a realistic 30-day movement history for the demo database (P24).

Every product gets a demand profile: ~30% steady sellers (a sale every
1-3 days), ~50% moderate (a sale every 4-10 days), ~20% slow movers
(0-2 sales a month) — plus periodic restocks. Reasons follow the app
taxonomy (sale / restock / write_off) so analytics and the dynamics
charts read naturally.

Usage (from the repo root or inside the container):
    python -m scripts.seed_movements            # add history
    python -m scripts.seed_movements --wipe     # wipe movements first

The wipe flag only touches stock_movements — product quantities are
left as they are (they already reflect the "current" state).
"""

import random
import sys
from datetime import datetime, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import psycopg

from database import get_connection_string

WIPE = "--wipe" in sys.argv
DAYS = 30
random.seed(20261024)


def main() -> None:
    conn = psycopg.connect(get_connection_string())
    cur = conn.cursor()

    if WIPE:
        cur.execute("DELETE FROM stock_movements")
        print("wiped stock_movements")

    cur.execute("SELECT id FROM products")
    product_ids = [row[0] for row in cur.fetchall()]
    if not product_ids:
        print("no products — run scripts.seed_demo_data first")
        conn.close()
        return

    now = datetime.now()
    start = now - timedelta(days=DAYS)
    movements = []

    for product_id in product_ids:
        roll = random.random()
        if roll < 0.30:
            sale_every, sale_qty = (1, 3), (1, 4)  # steady seller
        elif roll < 0.80:
            sale_every, sale_qty = (4, 10), (1, 3)  # moderate
        else:
            sale_every, sale_qty = (12, 30), (1, 2)  # slow mover

        day = random.uniform(0, sale_every[1])
        while day < DAYS:
            movements.append(
                (
                    product_id,
                    "out",
                    -random.randint(*sale_qty),
                    "sale",
                    start + timedelta(days=day, hours=random.uniform(0, 24) - 24),
                )
            )
            day += random.uniform(*sale_every)

        # A restock wave roughly every 10 days for active products.
        if roll < 0.80 and random.random() < 0.75:
            for wave in range(random.randint(1, 3)):
                movements.append(
                    (
                        product_id,
                        "in",
                        random.randint(8, 30),
                        "restock",
                        start
                        + timedelta(
                            days=random.uniform(0, DAYS),
                            hours=random.uniform(0, 24) - 24,
                        ),
                    )
                )

    # A few write-offs for realism.
    for product_id in random.sample(product_ids, min(40, len(product_ids))):
        movements.append(
            (
                product_id,
                "out",
                -random.randint(1, 3),
                "write_off",
                start + timedelta(days=random.uniform(0, DAYS)),
            )
        )

    cur.executemany(
        "INSERT INTO stock_movements (product_id, in_out, qty, reason, timestamp) "
        "VALUES (%s, %s, %s, %s, %s)",
        movements,
    )
    conn.commit()
    print(f"seeded {len(movements)} movements over {DAYS} days for {len(product_ids)} products")
    conn.close()


if __name__ == "__main__":
    main()
