#!/usr/bin/env python3
"""
Seed script for stock_movements table with 30 simulated movements over last 30 days.
Uses random data based on existing product quantities.
"""

import os
import random
from datetime import datetime, timedelta

# Connect to the test database (same as conftest.py)
TEST_DB = os.getenv("TEST_DB")
if not TEST_DB:
    raise ValueError("TEST_DB environment variable not set")

# Get connection string from conftest
import psycopg

conn = psycopg.connect(os.getenv("TEST_CONN_STRING"))
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
