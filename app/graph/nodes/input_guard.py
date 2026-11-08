from langchain_core.messages import AIMessage
from langgraph.runtime import Runtime

from app.core.logging import get_logger
from app.graph import prompts
from app.graph.context import RuntimeContext
from app.graph.state import AgentState
from app.guards.injection import scan

log = get_logger(__name__)


async def input_guard(state: AgentState, runtime: Runtime[RuntimeContext]) -> dict:
    check = scan(state["messages"][-1].content)
    if check.flagged:
        log.warning("injection_blocked", user=runtime.context.user_id, reasons=check.reasons)
    return {"guard": check.model_dump()}


def route_after_guard(state: AgentState) -> str:
    return "blocked_response" if state["guard"]["flagged"] else "supervisor"


async def blocked_response(state: AgentState) -> dict:
    return {"messages": [AIMessage(prompts.BLOCKED)]}
