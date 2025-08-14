import sqlite3


def execute_sql_query(sql_query: str) -> list[dict[str, object]]:
    """
    Executes a SQL query on the given SQLite database and returns the result as a list of dicts.

    Args:
        sql_query (str): The SQL query string to execute.
        database_path (str): Path to the SQLite database file.

    Returns:
        list: Query results as a list of dictionaries.
              If there's an error, returns [{"Error": "<message>"}].
    """
    # sql_query = """SELECT EXISTS (SELECT 1 FROM holidays WHERE holiday = \'Christmas\' AND year = 2025 AND city = \'Kolkata\')"""
    sql_query = """SELECT * FROM holidays WHERE holiday = 'Christmas' AND year = 2025 AND city = 'Kolkata'"""
    sql_query = sql_query.replace("\\", "")

    # try:
    connection = sqlite3.connect('ultimatix.db')

    cursor = connection.cursor()

    cursor.execute(sql_query)

    rows = cursor.fetchall()

    print(rows)

    columns = [desc[0] for desc in cursor.description]

    connection.close()

    return [dict(zip(columns, row)) for row in rows]
    # except Exception as e:
    #     return [{"Error": str(e)}]


print(execute_sql_query("a"))