from langgraph.runtime import Runtime
from pydantic import BaseModel, Field

from app.core.config import get_settings
from app.core.logging import get_logger
from app.core.rbac import can_research
from app.graph import prompts
from app.graph.context import RuntimeContext
from app.graph.state import AgentState, Route

log = get_logger(__name__)

NEXT_NODE = {"qa": "retrieval", "research": "research_plan", "tool": "tool_agent", "chitchat": "response"}


class RoutePlan(BaseModel):
    route: Route
    search_query: str = Field(max_length=300)
    rationale: str = Field(max_length=300)


def make_supervisor(llm):
    planner = llm.with_structured_output(RoutePlan)

    async def supervisor(state: AgentState, runtime: Runtime[RuntimeContext]) -> dict:
        system = prompts.SUPERVISOR.format(brand=get_settings().brand_name)
        plan: RoutePlan = await planner.ainvoke([("system", system), *state["messages"][-6:]])

        route, notice = plan.route, ""
        if route == "research" and not can_research(runtime.context.role):
            route, notice = "qa", prompts.RESEARCH_DOWNGRADED
            log.info("research_downgraded", role=runtime.context.role.value)

        log.info("supervisor_routed", route=route, rationale=plan.rationale)
        return {
            "route": route,
            "notice": notice,
            "search_query": plan.search_query,
            "rationale": plan.rationale,
            "retrieved": [],
            "dropped": [],
            "degraded": False,
            "draft": "",
            "attempts": 0,
            "validation": {},
            "plan_code": "",
            "batches": [],
            "findings": None,
            "research_errors": None,
            "analysis": {},
            "tools_bound": [],
            "tool_messages": None,
            "tool_results": [],
        }

    return supervisor


def route_after_supervisor(state: AgentState) -> str:
    return NEXT_NODE[state["route"]]
