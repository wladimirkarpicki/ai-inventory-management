from flask import (
    Flask,
    render_template,
    request,
    redirect,
    url_for
)

import psycopg

from database import get_connection_string


app = Flask(__name__)

PAGE_SIZE = 5


@app.route("/")
def home():
    return render_template("index.html")


@app.route("/products")
def products():

    page = request.args.get(
        "page",
        default=1,
        type=int
    )

    if page < 1:
        page = 1

    offset = (page - 1) * PAGE_SIZE

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
        LIMIT %s
        OFFSET %s
    """, (PAGE_SIZE, offset))

    products = cur.fetchall()

    cur.execute("""
        SELECT COUNT(*)
        FROM products
    """)

    total_products = cur.fetchone()[0]

    cur.close()
    conn.close()

    total_pages = (
        (total_products - 1) // PAGE_SIZE
    ) + 1 if total_products else 1

    return render_template(
        "products.html",
        products=products,
        page=page,
        total_pages=total_pages
    )


@app.route("/products/add", methods=["GET", "POST"])
def add_product():

    conn = psycopg.connect(get_connection_string())
    cur = conn.cursor()

    if request.method == "POST":

        brand_id = request.form["brand_id"]
        product_name = request.form["name"]
        price = request.form["price"]
        quantity = request.form["quantity"]

        cur.execute("""
            INSERT INTO products
                (
                    brand_id,
                    name,
                    price,
                    quantity
                )
            VALUES
                (%s, %s, %s, %s)
        """, (
            brand_id,
            product_name,
            price,
            quantity
        ))

        conn.commit()

        cur.close()
        conn.close()

        return redirect(url_for("products"))

    cur.execute("""
        SELECT
            id,
            name
        FROM brands
        ORDER BY id
    """)

    brands = cur.fetchall()

    cur.close()
    conn.close()

    return render_template(
        "add_product.html",
        brands=brands
    )


@app.route("/brands")
def brands():

    page = request.args.get(
        "page",
        default=1,
        type=int
    )

    if page < 1:
        page = 1

    offset = (page - 1) * PAGE_SIZE

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
        LIMIT %s
        OFFSET %s
    """, (PAGE_SIZE, offset))

    brands = cur.fetchall()

    cur.execute("""
        SELECT COUNT(*)
        FROM brands
    """)

    total_brands = cur.fetchone()[0]

    cur.close()
    conn.close()

    total_pages = (
        (total_brands - 1) // PAGE_SIZE
    ) + 1 if total_brands else 1

    return render_template(
        "brands.html",
        brands=brands,
        page=page,
        total_pages=total_pages
    )


if __name__ == "__main__":
    app.run(debug=True)