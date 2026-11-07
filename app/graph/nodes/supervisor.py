from langgraph.runtime import Runtime
from pydantic import BaseModel, Field

from app.core.config import get_settings
from app.core.logging import get_logger
from app.graph import prompts
from app.graph.context import RuntimeContext
from app.graph.state import AgentState, Route

log = get_logger(__name__)


class RoutePlan(BaseModel):
    route: Route
    search_query: str = Field(max_length=300)
    rationale: str = Field(max_length=300)


def make_supervisor(llm):
    planner = llm.with_structured_output(RoutePlan)

    async def supervisor(state: AgentState, runtime: Runtime[RuntimeContext]) -> dict:
        system = prompts.SUPERVISOR.format(brand=get_settings().brand_name)
        plan: RoutePlan = await planner.ainvoke([("system", system), *state["messages"][-6:]])

        log.info("supervisor_routed", route=plan.route, rationale=plan.rationale)
        return {
            "route": plan.route,
            "search_query": plan.search_query,
            "rationale": plan.rationale,
            "retrieved": [],
            "draft": "",
            "attempts": 0,
            "validation": {},
        }

    return supervisor


def route_after_supervisor(state: AgentState) -> str:
    return "retrieval" if state["route"] == "qa" else "response"
