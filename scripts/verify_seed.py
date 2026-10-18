import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import psycopg
from database import get_connection_string

with psycopg.connect(get_connection_string()) as c:
    rows = c.execute("SELECT brand_id, COUNT(*) FROM products GROUP BY brand_id ORDER BY COUNT(*) DESC LIMIT 5").fetchall()
    for brand_id, count in rows:
        print(f"brand_id={brand_id} count={count}")
    total = c.execute("SELECT COUNT(*) FROM products").fetchone()[0]
    print(f"total products: {total}")
    brands = c.execute("SELECT id, name FROM brands ORDER BY id").fetchall()
    print(f"brand count: {len(brands)}")
    print("first brands:", [b[1] for b in brands[:8]])
