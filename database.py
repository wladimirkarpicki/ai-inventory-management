import os

import psycopg
from dotenv import load_dotenv
from getpass import getpass


load_dotenv()


def get_connection_string():
    """
    Build the PostgreSQL connection string from environment variables.
    """

    host = os.getenv("DATABASE_HOST")
    database = os.getenv("DATABASE_NAME")
    user = os.getenv("DATABASE_USER")
    password = os.getenv("DATABASE_PASSWORD")

    if not all([host, database, user, password]):
        raise ValueError(
            "Database configuration is incomplete. "
            "Check your .env file."
        )

    return (
        f"postgresql://{user}:{password}@{host}/{database}"
    )


def connect_to_db():
    """
    Connect to the PostgreSQL database.

    Returns:
        tuple: (connection, cursor)
    """

    while True:
        try:
            connection_string = get_connection_string()

            conn = psycopg.connect(connection_string)
            cur = conn.cursor()

            print("\n✅ Connected successfully!\n")

            return conn, cur

        except psycopg.OperationalError:
            print(
                "\n❌ Unable to connect to the database."
                "\nPlease check your database configuration.\n"
            )

            break