from typing import TypedDict, Optional, List, Dict, Any


class AgentState(TypedDict):
    user_query: str
    sql_query: Optional[str]
    query_result: Optional[List[Dict[str, Any]]]
    database_schema: str
    final_answer: Optional[str]
    task: Optional[str]
