from typing import Annotated, Literal, TypedDict

from langchain_core.messages import AnyMessage
from langgraph.graph.message import add_messages

Route = Literal["qa", "research", "tool", "chitchat"]


def add_or_reset(current: list | None, update: list | None) -> list:
    if update is None:
        return []
    return (current or []) + update


class AgentState(TypedDict, total=False):
    messages: Annotated[list[AnyMessage], add_messages]
    route: Route
    rationale: str
    guard: dict
    dropped: list[str]
    notice: str
    search_query: str
    retrieved: list[dict]
    draft: str
    attempts: int
    validation: dict
    plan_code: str
    plan_rationale: str
    plan_source: str
    batches: list[list[str]]
    findings: Annotated[list[dict], add_or_reset]
    research_errors: Annotated[list[str], add_or_reset]
    analysis: dict
    tools_bound: list[str]
    tool_messages: Annotated[list[AnyMessage], add_or_reset]
    tool_results: list[dict]


class WorkerInput(TypedDict):
    batch: list[str]
    question: str
