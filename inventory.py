PAGE_SIZE = 5

def show_products(cur):
    """
    Display all products with pagination.
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


    if not products:
        print("\n❌ No products available.\n")
        return


    page = 0


    while True:

        total_pages = (
            (len(products) - 1) // PAGE_SIZE
        ) + 1


        start = page * PAGE_SIZE
        end = start + PAGE_SIZE


        print("\n================== Products ==================")
        print(
            f"Page {page + 1} of {total_pages}"
        )

        print(
            f"{'ID':<5}"
            f"{'Brand':<20}"
            f"{'Product':<25}"
            f"{'Price':<12}"
            f"{'Qty'}"
        )

        print("-" * 75)


        for product in products[start:end]:

            print(
                f"{product[0]:<5}"
                f"{product[1]:<20}"
                f"{product[2]:<25}"
                f"${product[3]:<11.2f}"
                f"{product[4]}"
            )


        print("\nCommands:")
        print("next - Next page")
        print("prev - Previous page")
        print("back - Return")


        command = input("\nYour choice: ").strip().lower()


        if command == "next":

            if page < total_pages - 1:
                page += 1

            else:
                print(
                    "\nAlready on the last page.\n"
                )


        elif command == "prev":

            if page > 0:
                page -= 1

            else:
                print(
                    "\nAlready on the first page.\n"
                )


        elif command == "back":

            break


        else:

            print(
                "\n❌ Unknown command.\n"
            )


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


def select_product(cur, brand_id):
    """
    Display products for selected brand and return product ID.
    """

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


    if not products:
        print(
            "\n❌ No products found for this brand.\n"
        )
        return None


    print("\n========== Available Products ==========")
    print(
        f"{'ID':<5}"
        f"{'Product':<25}"
        f"{'Price':<12}"
        f"{'Qty'}"
    )
    print("-" * 50)


    for product in products:
        print(
            f"{product[0]:<5}"
            f"{product[1]:<25}"
            f"${product[2]:<11.2f}"
            f"{product[3]}"
        )


    print()


    choice = input(
        "Choose product ID: "
    ).strip()


    if not choice.isdigit():
        print(
            "\n❌ Invalid product selection.\n"
        )
        return None


    product_id = int(choice)


    for product in products:
        if product[0] == product_id:
            return product_id


    print(
        "\n❌ Product not found.\n"
    )

    return None


def update_product(cur, conn):
    """
    Update product name, price, and quantity.
    """

    print("\n========== Update Product ==========")

    brand_id = select_brand(cur)

    if brand_id is None:
        return

    product_id = select_product(cur, brand_id)

    if product_id is None:
        return

    cur.execute("""
        SELECT
            name,
            price,
            quantity
        FROM products
        WHERE id = %s
    """, (product_id,))

    product = cur.fetchone()

    print("\nCurrent product:")
    print(f"Product: {product[0]}")
    print(f"Price: {product[1]:.2f}")
    print(f"Quantity: {product[2]}")

    new_name = input(
        "\nNew product name (Enter to keep current): "
    ).strip()

    new_price = input(
        "New price (Enter to keep current): "
    ).strip()

    new_quantity = input(
        "New quantity (Enter to keep current): "
    ).strip()

    if new_name == "":
        new_name = product[0]

    if new_price == "":
        new_price = product[1]
    else:
        try:
            new_price = float(new_price)

        except ValueError:
            print(
                "\n❌ Price must be a number.\n"
            )
            return

    if new_quantity == "":
        new_quantity = product[2]
    else:
        try:
            new_quantity = int(new_quantity)

        except ValueError:
            print(
                "\n❌ Quantity must be an integer.\n"
            )
            return

    cur.execute("""
        UPDATE products
        SET
            name = %s,
            price = %s,
            quantity = %s
        WHERE id = %s
    """,
    (
        new_name,
        new_price,
        new_quantity,
        product_id
    ))

    conn.commit()

    print(
        "\n✅ Product updated successfully.\n"
    )


def delete_product(cur, conn):
    """
    Delete a product from the inventory.
    """

    print("\n========== Delete Product ==========")

    brand_id = select_brand(cur)

    if brand_id is None:
        return

    product_id = select_product(cur, brand_id)

    if product_id is None:
        return

    cur.execute("""
        SELECT
            name,
            price,
            quantity
        FROM products
        WHERE id = %s
    """, (product_id,))

    product = cur.fetchone()

    print("\nYou are going to delete:")
    print(f"Product: {product[0]}")
    print(f"Price: {product[1]:.2f}")
    print(f"Quantity: {product[2]}")

    confirmation = input("\nAre you sure? (y/n): ").strip().lower()

    if confirmation != "y":
        print("\n❌ Delete cancelled.\n")
        return

    cur.execute("""
        DELETE FROM products
        WHERE id = %s
    """, (product_id,))

    conn.commit()

    print("\n✅ Product deleted successfully.\n")