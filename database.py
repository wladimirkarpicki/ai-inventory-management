import os

from dotenv import load_dotenv

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
        raise ValueError("Database configuration is incomplete. Check your .env file.")

    return f"postgresql://{user}:{password}@{host}/{database}"
