import psycopg
from getpass import getpass


def connect_to_db():
    """
    Connect to the PostgreSQL database.

    Returns:
        tuple: (connection, cursor)
    """

    while True:
        try:
            host = input("Enter database host (e.g., localhost): ")
            database = input("Enter database name: ")
            user = input("Enter username: ")
            password = getpass("Enter password: ")

            connection_string = (
                f"postgresql://{user}:{password}@{host}/{database}"
            )

            conn = psycopg.connect(connection_string)
            cur = conn.cursor()

            print("\n✅ Connected successfully!\n")

            return conn, cur

        except psycopg.OperationalError:
            print(
                "\n❌ Invalid credentials or connection details."
                "\nPlease try again.\n"
            )