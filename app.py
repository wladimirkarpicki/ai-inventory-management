import os

from decimal import (
    Decimal,
    InvalidOperation
)

from flask import (
    Flask,
    g,
    render_template,
    request,
    redirect,
    url_for
)

import psycopg

from database import get_connection_string


app = Flask(__name__)

PAGE_SIZE = 5


def get_db():
    """
    One PostgreSQL connection per request, closed automatically
    when the request ends.
    """

    if "db" not in g:
        g.db = psycopg.connect(get_connection_string())

    return g.db


@app.teardown_appcontext
def close_db(exc):
    """
    Close the request-scoped DB connection, if one was opened.
    """

    db = g.pop("db", None)

    if db is not None:
        db.close()


@app.errorhandler(psycopg.OperationalError)
def db_unavailable(exc):
    """
    Show a friendly page instead of a traceback when the
    database cannot be reached.
    """

    return render_template(
        "error.html",
        message="Database unavailable. Please check that PostgreSQL is running and try again."
    ), 503


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

    search = request.args.get("search", "").strip()

    offset = (page - 1) * PAGE_SIZE

    conn = get_db()
    cur = conn.cursor()

    if search:
        pattern = f"%{escape_like(search)}%"
        query_args = (pattern, pattern)

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
            WHERE p.name ILIKE %s ESCAPE '\\'
                OR b.name ILIKE %s ESCAPE '\\'
            ORDER BY b.name, p.name
            LIMIT %s
            OFFSET %s
        """, query_args + (PAGE_SIZE, offset))

        products = cur.fetchall()

        cur.execute("""
            SELECT COUNT(*)
            FROM products p
            JOIN brands b
                ON p.brand_id = b.id
            WHERE p.name ILIKE %s ESCAPE '\\'
                OR b.name ILIKE %s ESCAPE '\\'
        """, query_args)

        total_products = cur.fetchone()[0]

    else:
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

    total_pages = (
        (total_products - 1) // PAGE_SIZE
    ) + 1 if total_products else 1

    return render_template(
        "products.html",
        products=products,
        page=page,
        total_pages=total_pages,
        search=search
    )


@app.route("/products/add", methods=["GET", "POST"])
def add_product():

    error = None
    form = {
        "name": "",
        "price": "",
        "quantity": "",
        "brand_id": None
    }

    conn = get_db()
    cur = conn.cursor()

    if request.method == "POST":

        form["name"] = request.form.get("name", "").strip()
        form["price"] = request.form.get("price", "").strip()
        form["quantity"] = request.form.get("quantity", "").strip()

        raw_brand_id = request.form.get("brand_id", "")

        if raw_brand_id.isdigit():
            form["brand_id"] = int(raw_brand_id)

            cur.execute(
                "SELECT 1 FROM brands WHERE id = %s",
                (form["brand_id"],)
            )

            if cur.fetchone() is None:
                error = "Selected brand does not exist."
        else:
            error = "Please select a brand."

        if error is None:
            error = validate_product_name(form["name"])

        if error is None:
            error, price = parse_price(form["price"])

        if error is None:
            error, quantity = parse_quantity(form["quantity"])

        if error is None:
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
                form["brand_id"],
                form["name"],
                price,
                quantity
            ))

            conn.commit()

            return redirect(url_for("products"))

    cur.execute("""
        SELECT
            id,
            name
        FROM brands
        ORDER BY id
    """)

    brands = cur.fetchall()

    return render_template(
        "add_product.html",
        brands=brands,
        error=error,
        form=form
    )


@app.route("/products/edit", methods=["GET", "POST"])
def edit_product():

    brand_id = request.args.get(
        "brand_id",
        type=int
    )

    product_id = request.args.get(
        "product_id",
        type=int
    )

    conn = get_db()
    cur = conn.cursor()

    # POST: save changes
    if request.method == "POST":

        if product_id is None:
            return "Product ID is required", 400

        cur.execute(
            "SELECT id FROM products WHERE id = %s",
            (product_id,)
        )

        if cur.fetchone() is None:
            return "Product not found", 404

        name = request.form.get("name", "").strip()
        raw_price = request.form.get("price", "").strip()
        raw_quantity = request.form.get("quantity", "").strip()

        error = validate_product_name(name)

        if error is None:
            error, price = parse_price(raw_price)

        if error is None:
            error, quantity = parse_quantity(raw_quantity)

        if error is None:
            cur.execute("""
                UPDATE products
                SET
                    name = %s,
                    price = %s,
                    quantity = %s
                WHERE id = %s
            """, (
                name,
                price,
                quantity,
                product_id
            ))

            conn.commit()

            return redirect(url_for("products"))

        product = (product_id, None, name, raw_price, raw_quantity)

        return render_template(
            "edit_product.html",
            product=product,
            error=error
        )

    # GET: no selection yet → show brands
    if brand_id is None and product_id is None:

        cur.execute("""
            SELECT
                id,
                name
            FROM brands
            ORDER BY id
        """)

        brands = cur.fetchall()

        return render_template(
            "edit_product_brand.html",
            brands=brands
        )

    # GET: brand selected → show products
    if product_id is None:

        cur.execute("""
            SELECT
                id,
                name,
                price,
                quantity
            FROM products
            WHERE brand_id = %s
            ORDER BY id
        """, (brand_id,))

        products = cur.fetchall()

        return render_template(
            "edit_product_select.html",
            products=products,
            brand_id=brand_id
        )

    # GET: product selected → show edit form
    cur.execute("""
        SELECT
            id,
            brand_id,
            name,
            price,
            quantity
        FROM products
        WHERE id = %s
    """, (product_id,))

    product = cur.fetchone()

    if product is None:
        return "Product not found", 404

    return render_template(
        "edit_product.html",
        product=product
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

    conn = get_db()
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

    total_pages = (
        (total_brands - 1) // PAGE_SIZE
    ) + 1 if total_brands else 1

    return render_template(
        "brands.html",
        brands=brands,
        page=page,
        total_pages=total_pages
    )


@app.route("/products/delete", methods=["GET", "POST"])
def delete_product():

    brand_id = request.args.get(
        "brand_id",
        type=int
    )

    product_id = request.args.get(
        "product_id",
        type=int
    )

    conn = get_db()
    cur = conn.cursor()

    # POST: delete the selected product
    if request.method == "POST":

        if product_id is None:
            return "Product ID is required", 400

        cur.execute("""
            DELETE FROM products
            WHERE id = %s
        """, (product_id,))

        if cur.rowcount == 0:
            conn.rollback()

            return "Product not found", 404

        conn.commit()

        return redirect(url_for("products"))

    # GET: no selection yet → show brands
    if brand_id is None and product_id is None:

        cur.execute("""
            SELECT
                id,
                name
            FROM brands
            ORDER BY id
        """)

        brands = cur.fetchall()

        return render_template(
            "delete_product_brand.html",
            brands=brands
        )

    # GET: brand selected → show products
    if product_id is None:

        cur.execute("""
            SELECT
                id,
                name,
                price,
                quantity
            FROM products
            WHERE brand_id = %s
            ORDER BY id
        """, (brand_id,))

        products = cur.fetchall()

        return render_template(
            "delete_product_select.html",
            products=products,
            brand_id=brand_id
        )

    # GET: product selected → show confirmation
    cur.execute("""
        SELECT
            id,
            brand_id,
            name,
            price,
            quantity
        FROM products
        WHERE id = %s
    """, (product_id,))

    product = cur.fetchone()

    if product is None:
        return "Product not found", 404

    return render_template(
        "delete_product_confirm.html",
        product=product
    )


def escape_like(term):
    """
    Escape LIKE wildcards in a search term so they match literally.
    """

    return (
        term
        .replace("\\", "\\\\")
        .replace("%", "\\%")
        .replace("_", "\\_")
    )


def validate_product_name(name):
    """
    Validate a product name.
    Returns an error message string, or None when the name is valid.
    """

    if not name:
        return "Product name is required."

    return None


def parse_price(raw):
    """
    Parse and validate a price.
    Returns (error, price); price is a Decimal when error is None.
    """

    try:
        price = Decimal(raw)
    except (InvalidOperation, ValueError):
        return "Price must be a number.", None

    if not price.is_finite() or price < 0:
        return "Price must be a non-negative number.", None

    return None, price


def parse_quantity(raw):
    """
    Parse and validate a quantity.
    Returns (error, quantity); quantity is an int when error is None.
    """

    try:
        quantity = int(raw)
    except (ValueError, TypeError):
        return "Quantity must be an integer.", None

    if quantity < 0:
        return "Quantity must be a non-negative integer.", None

    return None, quantity


def validate_brand_name(name):
    """
    Validate a brand name for add / edit operations.
    Returns an error message string, or None when the name is valid.
    """

    if not name:
        return "Brand name is required."

    if len(name) > 100:
        return "Brand name must be 100 characters or fewer."

    return None


@app.route("/brands/add", methods=["GET", "POST"])
def add_brand():

    name = ""
    error = ""

    if request.method == "POST":

        name = request.form.get("name", "").strip()
        error = validate_brand_name(name)

        if error is None:

            try:
                conn = get_db()
                cur = conn.cursor()

                cur.execute(
                    "SELECT 1 FROM brands WHERE LOWER(name) = LOWER(%s)",
                    (name,)
                )

                if cur.fetchone() is not None:
                    error = f'A brand named "{name}" already exists.'
                else:
                    cur.execute(
                        "INSERT INTO brands (name) VALUES (%s)",
                        (name,)
                    )

                    conn.commit()

            except psycopg.errors.UniqueViolation:
                error = f'A brand named "{name}" already exists.'

        if error is None:
            return redirect(url_for("brands"))

    return render_template("add_brand.html", name=name, error=error)


@app.route("/brands/edit", methods=["GET", "POST"])
def edit_brand():

    brand_id = request.args.get(
        "brand_id",
        type=int
    )

    # POST: save changes
    if request.method == "POST":

        name = request.form.get("name", "").strip()
        error = validate_brand_name(name)
        success = False

        try:
            conn = get_db()
            cur = conn.cursor()

            cur.execute(
                "SELECT id, name FROM brands WHERE id = %s",
                (brand_id,)
            )

            row = cur.fetchone()

            if row is None:
                return "Brand not found", 404

            if error is None:
                cur.execute(
                    "SELECT id FROM brands WHERE LOWER(name) = LOWER(%s) AND id <> %s",
                    (name, brand_id)
                )

                if cur.fetchone() is not None:
                    error = f'A brand named "{name}" already exists.'

            if error is None:
                cur.execute(
                    "UPDATE brands SET name = %s WHERE id = %s",
                    (name, brand_id)
                )

                conn.commit()
                success = True

        except psycopg.errors.UniqueViolation:
            error = f'A brand named "{name}" already exists.'

        if success:
            return redirect(url_for("brands"))

        # Re-display the submitted name when editing after a validation error
        brand = (brand_id, name)

        return render_template("edit_brand.html", brand=brand, error=error)

    # GET: no selection yet -> show brand picker
    if brand_id is None:

        conn = get_db()
        cur = conn.cursor()

        cur.execute("""
            SELECT
                id,
                name
            FROM brands
            ORDER BY id
        """)

        brands = cur.fetchall()

        return render_template("edit_brand_select.html", brands=brands)

    # GET: brand selected -> show edit form
    conn = get_db()
    cur = conn.cursor()

    cur.execute(
        "SELECT id, name FROM brands WHERE id = %s",
        (brand_id,)
    )

    brand = cur.fetchone()

    if brand is None:
        return "Brand not found", 404

    return render_template("edit_brand.html", brand=brand, error="")


@app.route("/brands/delete", methods=["GET", "POST"])
def delete_brand():

    brand_id = request.args.get("brand_id", type=int)

    # POST: delete brand
    if request.method == "POST":

        if brand_id is None:
            return "Brand ID is required", 400

        conn = get_db()
        cur = conn.cursor()

        cur.execute("SELECT id, name FROM brands WHERE id = %s", (brand_id,))
        brand = cur.fetchone()

        if brand is None:
            return "Brand not found", 404

        try:
            cur.execute("DELETE FROM brands WHERE id = %s", (brand_id,))
            conn.commit()
        except psycopg.errors.ForeignKeyViolation:
            conn.rollback()
            return render_template(
                "delete_brand_confirm.html",
                brand=brand,
                error="This brand has products and cannot be deleted."
            )

        return redirect(url_for("brands"))

    # GET: no selection -> show picker
    if brand_id is None:

        conn = get_db()
        cur = conn.cursor()

        cur.execute("""
            SELECT id, name
            FROM brands
            ORDER BY id
        """)

        brands = cur.fetchall()

        return render_template("delete_brand_select.html", brands=brands)

    # GET: brand selected -> show confirmation
    conn = get_db()
    cur = conn.cursor()

    cur.execute("SELECT id, name FROM brands WHERE id = %s", (brand_id,))
    brand = cur.fetchone()

    if brand is None:
        return "Brand not found", 404

    return render_template("delete_brand_confirm.html", brand=brand)


if __name__ == "__main__":
    app.run(debug=os.getenv("FLASK_DEBUG") == "1")

