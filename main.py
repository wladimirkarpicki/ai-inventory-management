from database import connect_to_db
from inventory import (
    show_products,
    show_brands,
    search_product,
    add_product,
    update_product,
    delete_product
)


def main():

    conn, cur = connect_to_db()

    try:

        while True:

            print("========== Inventory Management ==========")
            print("1. View all products")
            print("2. Show brands")
            print("3. Search product")
            print("4. Add product")
            print("5. Update product")
            print("6. Delete product")
            print("7. Exit")

            choice = input("\nChoose an option: ").strip()

            if choice == "1":
                show_products(cur)

            elif choice == "2":
                show_brands(cur)

            elif choice == "3":
                search_product(cur)

            elif choice == "4":
                add_product(cur, conn)

            elif choice == "5":
                update_product(cur, conn)

            elif choice == "6":
                delete_product(cur, conn)

            elif choice == "7":
                print("\nGoodbye!")
                break

            else:
                print("\n❌ Invalid option.\n")

    finally:

        cur.close()
        conn.close()

        print("Database connection closed.")


if __name__ == "__main__":
    main()