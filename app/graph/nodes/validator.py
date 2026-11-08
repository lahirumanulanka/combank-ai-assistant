from langchain_core.messages import AIMessage

from app.core.logging import get_logger
from app.graph import prompts
from app.graph.state import AgentState
from app.guards.brand import check_brand
from app.guards.citations import check_citations

log = get_logger(__name__)

MAX_ATTEMPTS = 2
CITED_ROUTES = {"qa", "research", "tool"}


def decide(state: AgentState, result: dict, fallback: str) -> dict:
    if result["ok"]:
        return {"validation": result, "messages": [AIMessage(state["draft"])]}
    if state["attempts"] < MAX_ATTEMPTS:
        return {"validation": result}
    return {"validation": result, "messages": [AIMessage(fallback)]}


async def validator(state: AgentState) -> dict:
    draft = state["draft"]

    brand = check_brand(draft)
    if not brand.ok:
        log.warning("brand_violation", reason=brand.reason, attempt=state["attempts"])
        result = {"ok": False, "brand_ok": False, "cited": [], "unknown": [], "reason": brand.reason}
        return decide(state, result, fallback=prompts.BRAND_SAFE)

    if state["route"] not in CITED_ROUTES or draft == prompts.NOT_FOUND:
        return decide(state, {"ok": True, "brand_ok": True, "cited": [], "unknown": [], "reason": ""}, "")

    retrieved_ids = [chunk["chunk_id"] for chunk in state.get("retrieved", [])]
    check = check_citations(draft, retrieved_ids, require=state["route"] != "tool")
    log.info("validation", ok=check.ok, cited=check.cited, unknown=check.unknown, attempt=state["attempts"])
    return decide(state, {**check.model_dump(), "brand_ok": True}, fallback=prompts.UNVERIFIED)


def route_after_validation(state: AgentState) -> str:
    if state["validation"]["ok"] or state["attempts"] >= MAX_ATTEMPTS:
        return "done"
    return "tool_agent" if state["route"] == "tool" else "response"
