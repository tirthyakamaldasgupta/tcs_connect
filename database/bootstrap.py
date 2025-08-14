import os
import sqlite3
from dotenv import load_dotenv


load_dotenv()


def bootstrap() -> bool:
    """
    Initializes the database by creating it and applying schema and fixture scripts if it does not already exist.

    Returns:
        bool: True if the database already exists or was successfully initialized.

    Process:
        - Checks if the database file exists using the path from the "DATABASE_NAME" environment variable.
        - If not, creates a new SQLite database file.
        - Executes SQL schema from 'database/migrations/schema.sql'.
        - Executes all SQL fixture files found in 'database/fixtures/' directory.
        - Commits changes and closes the connection.
    """
    if os.path.exists(f"{os.environ['DATABASE_NAME']}.db"):
        return True

    connection = sqlite3.connect(f'{os.environ["DATABASE_NAME"]}.db')

    cursor = connection.cursor()

    with open(f"database/migrations/schema.sql", "r") as file:
        cursor.executescript(file.read())

        connection.commit()

    for filename in os.listdir("database/fixtures"):
        with open(f"database/fixtures/{filename}", "r") as file:
            cursor.executescript(file.read())

            connection.commit()

    connection.close()

    return True
