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