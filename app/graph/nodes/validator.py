from langchain_core.messages import AIMessage

from app.core.logging import get_logger
from app.graph import prompts
from app.graph.state import AgentState
from app.guards.citations import check_citations

log = get_logger(__name__)

MAX_ATTEMPTS = 2


def needs_citations(state: AgentState) -> bool:
    return state["route"] == "qa" and state["draft"] != prompts.NOT_FOUND


async def validator(state: AgentState) -> dict:
    if not needs_citations(state):
        return {"validation": {"ok": True}, "messages": [AIMessage(state["draft"])]}

    retrieved_ids = [chunk["chunk_id"] for chunk in state.get("retrieved", [])]
    check = check_citations(state["draft"], retrieved_ids)
    log.info("validation", ok=check.ok, cited=check.cited, unknown=check.unknown, attempt=state["attempts"])

    if check.ok:
        return {"validation": check.model_dump(), "messages": [AIMessage(state["draft"])]}
    if state["attempts"] < MAX_ATTEMPTS:
        return {"validation": check.model_dump()}
    return {"validation": check.model_dump(), "messages": [AIMessage(prompts.UNVERIFIED)]}


def route_after_validation(state: AgentState) -> str:
    if state["validation"]["ok"] or state["attempts"] >= MAX_ATTEMPTS:
        return "done"
    return "retry"
