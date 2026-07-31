def show_products(cur):
    """
    Display all products in the inventory.
    """

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

    print("\n================== Products ==================")
    print(f"{'ID':<5}{'Brand':<20}{'Product':<25}{'Price':<12}{'Qty'}")
    print("-" * 75)

    for product in products:
        print(
            f"{product[0]:<5}"
            f"{product[1]:<20}"
            f"{product[2]:<25}"
            f"${product[3]:<11.2f}"
            f"{product[4]}"
        )

    print()


def search_product(cur):
    """
    Search products by name.
    """

    search_term = input(
        "\nEnter product name to search: "
    ).strip()

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
        WHERE p.name ILIKE %s
        ORDER BY p.name
    """, (f"%{search_term}%",))

    products = cur.fetchall()

    if not products:
        print(
            f"\n❌ No products found for '{search_term}'.\n"
        )
        return

    print("\n================== Search Results ==================")
    print(f"{'ID':<5}{'Brand':<20}{'Product':<25}{'Price':<12}{'Qty'}")
    print("-" * 75)

    for product in products:
        print(
            f"{product[0]:<5}"
            f"{product[1]:<20}"
            f"{product[2]:<25}"
            f"${product[3]:<11.2f}"
            f"{product[4]}"
        )

    print()


def select_brand(cur):
    """
    Display available brands and return selected brand ID.
    """

    cur.execute("""
        SELECT
            id,
            name
        FROM brands
        ORDER BY id
    """)

    brands = cur.fetchall()

    if not brands:
        print("\n❌ No brands available.\n")
        return None


    print("\n========== Available Brands ==========")

    for brand in brands:
        print(
            f"{brand[0]} - {brand[1]}"
        )

    print()


    choice = input(
        "Choose brand ID: "
    ).strip()


    if not choice.isdigit():
        print("\n❌ Invalid brand selection.\n")
        return None


    brand_id = int(choice)


    for brand in brands:
        if brand[0] == brand_id:
            return brand_id


    print("\n❌ Brand not found.\n")
    return None


def add_product(cur, conn):
    """
    Add a new product to the inventory.
    """

    print("\n========== Add New Product ==========")


    brand_id = select_brand(cur)

    if brand_id is None:
        return


    product_name = input(
        "Enter product name: "
    ).strip()


    price = input(
        "Enter product price: "
    ).strip()


    quantity = input(
        "Enter product quantity: "
    ).strip()


    try:
        price = float(price)
        quantity = int(quantity)

    except ValueError:
        print(
            "\n❌ Price must be a number "
            "and quantity must be an integer.\n"
        )
        return


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
        RETURNING id
    """,
    (
        brand_id,
        product_name,
        price,
        quantity
    ))


    product_id = cur.fetchone()[0]


    conn.commit()


    print(
        f"\n✅ Product added successfully!"
        f"\nNew product ID: {product_id}\n"
    )