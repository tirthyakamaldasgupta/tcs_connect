import asyncio
import json
import os
import sqlite3
from agents import Agent, Runner, StopAtTools, function_tool
from dotenv import load_dotenv
from database.bootstrap import bootstrap as bootstrap_database
# import logging
# import sys


# logging.basicConfig(level=logging.DEBUG, stream=sys.stdout)


@function_tool
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
    sql_query = sql_query.replace("\\", "")

    try:
        cursor.execute(sql_query)

        rows = cursor.fetchall()

        columns = [desc[0] for desc in cursor.description]

        return [dict(zip(columns, row)) for row in rows]
    except Exception as e:
        return [{"Error": str(e)}]


load_dotenv()

environment = os.environ["ENVIRONMENT"]

if environment == "development":
    bootstrap_database()

connection = sqlite3.connect(f'{os.environ["DATABASE_NAME"]}.db')

cursor = connection.cursor()

cursor.execute(
    """
    SELECT name, sql
    FROM sqlite_master
    WHERE type='table';
    """
)

tables = [{"name": name, "sql": sql} for name, sql in cursor.fetchall()]

tables_json = json.dumps(tables, indent=2)


database_results_formatter_agent = Agent(
    name="Database Results Formatter Agent",
    model="litellm/mistral/mistral-small-2503",
    instructions="""
    You are an expert at creating human-friendly summaries from raw data.

    Your task is to take two inputs:
    1. A natural language question from a user.
    2. Raw data from a database query, formatted as a Python list of dictionaries.

    Based on these inputs, generate a concise, easy-to-read summary in plain English.
    
    Here are the rules you must follow:
    - **No results:** If the provided data is an empty list, respond with "No results found for your query."
    - **Errors:** If the data contains an error message (e.g., `[{"Error": "<message>"}]`), explain the error simply and tell the user to try again. Do not invent a solution.
    - **Formatting:** Use the original question as context to shape your answer. Do not just print the raw data.
    - **Clarity:** Keep the response natural and avoid technical jargon or a robotic tone.
    - **No other tasks:** Do not perform any other tasks, like making additional tool calls or generating new SQL queries.
    """,
)

database_agent = Agent(
    name="Database Agent",
    model="litellm/mistral/mistral-small-2503",
    instructions=f"Executes SQL queries against the '{os.environ['DATABASE_NAME']}' database.",
    tools=[execute_sql_query],
)

text_to_sql_agent = Agent(
    name="Text To SQL Agent",
    model="litellm/mistral/mistral-medium-2505",
    instructions=f"""
    You are a highly skilled SQL expert. Your sole purpose is to convert natural language questions into valid SQLite SQL queries.
    
    Database Schema:
    {tables_json}

    Requirements:
    - **Output Format:** Your response MUST contain ONLY the SQL query string. Do not include any additional text, explanations, code fences (```sql), or markdown.
    - **Query Type:** Always generate a query that selects all columns (`SELECT *`) from the `holidays` table, with a `WHERE` clause to filter the results. **Do not generate `SELECT EXISTS` or any other boolean-checking queries.**
    - **Escaping Characters:** When using string literals in the WHERE clause, do not use backslashes (\\). Use a pair of single quotes ('') for escaping if needed.
    - **Table Context:** Use only the `holidays` table and its columns as defined in the schema.
    - **Invalid Questions:** If a question cannot be answered with the provided schema, respond with the exact phrase "INVALID_QUERY".
    - **Error Avoidance:** Generate syntactically correct and executable SQL queries.
    """,
)

hr_agent = Agent(
    name="HR Agent",
    model="litellm/mistral/mistral-small-2503",
    instructions="""
    You are the Human Resources Agent for TCS Connect. You answer questions about company holidays.
    
    You must follow this multi-step process precisely:
    
    1.  **Generate SQL Query:** Use the `generate_sql_query` tool with the user's original question.
    
    2.  **Execute Query:** Use the `execute_database_query` tool with the query string from the previous step. **You must not stop here; you must continue the process.**
    
    3.  **Format Response:** Use the `format_database_results_response` tool with the raw results from the database (from step 2) AND the user's original question. This is the **only** step that should produce the final user-facing answer.
    
    **Crucial Rules:**
    -   You MUST perform these three steps in a single, continuous chain.
    -   Do not respond with a tool call in a text format. You must actually **call** the tool.
    -   Do not produce any other output until the `format_database_results_response` tool has completed.
    -   If any step fails, report the error to the user and stop.
    -   Return the output of the `format_database_results_response` tool to the user.
    """,
    tools=[
        text_to_sql_agent.as_tool(
            tool_name="generate_sql_query",
            tool_description="""Generates a SQL query string based on a user's question about holidays. The output is a raw SQL query.
            """,
        ),
        database_agent.as_tool(
            tool_name="execute_database_query",
            tool_description="""Executes a SQL query on the database and returns the raw results. This tool receives a cleaned SQL string as input.
            """,
        ),
        database_results_formatter_agent.as_tool(
            tool_name="format_database_results_response",
            tool_description="""Creates a final, user-friendly response from the raw database results.
            """,
        ),
    ],
)

triage_agent = Agent(
    name="Triage Agent",
    model="litellm/mistral/mistral-small-2503",
    instructions="""
    You are the Triage Agent for TCS Connect. Your purpose is to analyze each incoming user request and route it to the most appropriate specialist agent.

    Your current capabilities are limited to routing to a single specialist: the HR Agent.
    
    HR Agent's Scope:
    - The HR Agent exclusively handles queries about official holidays in India as stored in the `holidays` table in the 'ultimatix' database.
    - Topics include dates, days, months, city/state specifics, tentative/confirmed status, and holiday lists for a specific period.
    
    Routing Rules:
    - **Handoff:** If a request is unequivocally about Indian holidays and requires a database lookup, you MUST hand off to the HR Agent.
    - **Fallback:** For all other requests—including those related to payroll, recruitment, benefits, general HR policies, or any topic outside of Indian holidays—do NOT hand off. Instead, respond with "I'm sorry, I am not equipped to handle that type of query at this moment. I can only answer questions about Indian holidays."
    
    **When in doubt, default to the fallback response.** Do not hand off to the HR Agent unless the query clearly and directly relates to the defined scope.
    """,
    handoffs=[
        hr_agent,
    ],
)


async def main():
    result = await Runner.run(
        triage_agent,
        input="Is Christmas a holiday in 2025 in Kolkata?",
    )

    print(result)

    print(result.final_output)

    print(result.raw_responses)


if __name__ == "__main__":
    asyncio.run(main())
