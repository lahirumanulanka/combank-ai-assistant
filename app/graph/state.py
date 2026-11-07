from typing import Annotated, Literal, TypedDict

from langchain_core.messages import AnyMessage
from langgraph.graph.message import add_messages

Route = Literal["qa", "chitchat"]


class AgentState(TypedDict, total=False):
    messages: Annotated[list[AnyMessage], add_messages]
    route: Route
    rationale: str
    search_query: str
    retrieved: list[dict]
