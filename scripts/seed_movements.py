#!/usr/bin/env python3
"""
Seed script for stock_movements table with 30 simulated movements over last 30 days.
Uses random data based on existing product quantities.
"""

import random
import sys
from datetime import datetime, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import psycopg

from database import get_connection_string

conn = psycopg.connect(get_connection_string())
cur = conn.cursor()

# Generate 30 simulated movements
random.seed(42)  # For reproducibility

# Get all product IDs
cur.execute("SELECT id FROM products")
product_ids = [row[0] for row in cur.fetchall()]

# Current date
now = datetime.now()

# Generate 30 days of simulated movements (backwards from today)
start_date = now - timedelta(days=30)
movements = []

for i in range(30):
    # Random product
    product_id = random.choice(product_ids)

    # Random type: in or out (50/50 chance)
    movement_type = random.choice(['in', 'out'])

    # Random quantity (1-10 for in, 1-5 for out to keep quantities reasonable)
    if movement_type == 'in':
        qty = random.randint(1, 10)
    else:
        qty = random.randint(1, 5)

    # Calculate date (going backwards from today)
    movement_date = start_date + timedelta(days=i)

    # Random reason
    reasons = [
        "Initial stock",
        "Restock",
        "Sale",
        "Damage",
        "Return",
        "Transfer",
        "Reorder",
        "Inventory audit",
        "Promotion",
        "Seasonal demand"
    ]
    reason = random.choice(reasons)

    # Determine if qty should be positive or negative
    qty_value = qty if movement_type == 'in' else -qty

    movements.append((product_id, movement_type, qty_value, reason, movement_date))

# Insert all movements
cur.executemany("""
    INSERT INTO stock_movements (product_id, in_out, qty, reason, timestamp)
    VALUES (%s, %s, %s, %s, %s)
""", movements)

conn.commit()
conn.close()
print(f"Seeded {len(movements)} stock movements")
