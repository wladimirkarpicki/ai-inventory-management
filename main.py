from database import connect_to_db
from inventory import show_products, search_product, add_product


def main():

    conn, cur = connect_to_db()

    try:

        while True:

            print("========== Inventory Management ==========")
            print("1. View all products")
            print("2. Search product")
            print("3. Add product")
            print("4. Update product")
            print("5. Delete product")
            print("6. Exit")

            choice = input("\nChoose an option: ").strip()

            if choice == "1":
                show_products(cur)

            elif choice == "2":
                search_product(cur)

            elif choice == "3":
                add_product(cur, conn)

            elif choice == "4":
                print("Update product - Coming soon.\n")

            elif choice == "5":
                print("Delete product - Coming soon.\n")

            elif choice == "6":
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