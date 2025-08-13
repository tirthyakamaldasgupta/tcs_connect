import re
from langgraph.graph import StateGraph, END
from langchain.chat_models import init_chat_model
import json
import sqlite3
import os
from dotenv import load_dotenv
from typing import TypedDict, Optional, List, Dict, Any


class AgentState(TypedDict):
    user_query: str
    sql_query: Optional[str]
    query_result: Optional[List[Dict[str, Any]]]
    database_schema: str
    final_answer: Optional[str]
    task: Optional[str]


def clean_sql(sql_query: str) -> str:
    # Remove Markdown code fences and "sql" labels
    return re.sub(r"```(?:sql)?\s*|\s*```", "", sql_query).strip()


load_dotenv()

# --- DB Connection ---
conn = sqlite3.connect("ultimatix.db")
cursor = conn.cursor()

# --- Get schema dynamically ---
cursor.execute(
    """
    SELECT name, sql
    FROM sqlite_master
    WHERE type='table';
"""
)
tables = [{"name": name, "sql": sql} for name, sql in cursor.fetchall()]
tables_json = json.dumps(tables, indent=2)

# --- Initialize LLM ---
llm = init_chat_model("codestral-2501", model_provider="mistralai")


# --- LangGraph nodes ---
def classify_task(state: AgentState) -> AgentState:
    state["task"] = "holiday_db_lookup"
    return state


def generate_sql(state: AgentState) -> AgentState:
    prompt = f"""
    You are a SQL expert. Using the SQLite database schema below, write a valid SQL query
    to answer the question. Return ONLY the SQL.

    Schema:
    {state['database_schema']}

    Question: {state['user_query']}

    SQL:
    """
    resp = llm.invoke(prompt)
    state["sql_query"] = clean_sql(resp.content.strip())
    return state


def execute_sql(state: AgentState) -> AgentState:
    try:
        cursor.execute(state["sql_query"])
        rows = cursor.fetchall()
        columns = [desc[0] for desc in cursor.description]
        state["query_result"] = [dict(zip(columns, row)) for row in rows]
    except Exception as e:
        state["query_result"] = [{"Error": str(e)}]
    return state


def format_response(state: AgentState) -> AgentState:
    prompt = f"""
    The user asked: {state['user_query']}

    The generated SQL was:
    {state['sql_query']}

    The SQL execution result was:
    {state['query_result']}

    Write a clear, concise natural language answer for the user.
    """
    
    response = llm.invoke(prompt)
    
    state["final_answer"] = response

    return state


# --- LangGraph flow ---
graph = StateGraph(AgentState)
graph.add_node("classifier", classify_task)
graph.add_node("sql_generator", generate_sql)
graph.add_node("sql_executor", execute_sql)
graph.add_node("responder", format_response)

graph.set_entry_point("classifier")
graph.add_edge("classifier", "sql_generator")
graph.add_edge("sql_generator", "sql_executor")
graph.add_edge("sql_executor", "responder")
graph.add_edge("responder", END)

# --- Compile ---
app = graph.compile()

# --- Run the agent ---
initial_state: AgentState = {
    "user_query": "Give me the details of the holidays in Goa in 2025?",
    "sql_query": None,
    "query_result": None,
    "database_schema": tables_json,
    "final_answer": None,
    "task": None,
}

final_state = app.invoke(initial_state)
print(final_state["final_answer"])
