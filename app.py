from flask import Flask, render_template

import psycopg

from database import get_connection_string


app = Flask(__name__)


@app.route("/")
def home():
    return render_template("index.html")


@app.route("/products")
def products():
    conn = psycopg.connect(get_connection_string())
    cur = conn.cursor()

    cur.execute("""
        SELECT
            p.id,
            b.name,
            p.name,
            p.price,
            p.quantity
        FROM products p
        JOIN brands b
            ON p.brand_id = b.id
        ORDER BY b.name, p.name
    """)

    products = cur.fetchall()

    cur.close()
    conn.close()

    return render_template(
        "products.html",
        products=products
    )


@app.route("/brands")
def brands():
    conn = psycopg.connect(get_connection_string())
    cur = conn.cursor()

    cur.execute("""
        SELECT
            b.id,
            b.name,
            COUNT(p.id) AS product_count
        FROM brands b
        LEFT JOIN products p
            ON b.id = p.brand_id
        GROUP BY b.id, b.name
        ORDER BY b.id
    """)

    brands = cur.fetchall()

    cur.close()
    conn.close()

    return render_template(
        "brands.html",
        brands=brands
    )


if __name__ == "__main__":
    app.run(debug=True)
