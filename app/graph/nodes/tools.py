import asyncio

from langchain_core.messages import AIMessage, ToolMessage
from langgraph.runtime import Runtime
from langgraph.types import interrupt

from app.core.config import get_settings
from app.core.logging import get_logger
from app.core.rbac import Role, can_use_tool, needs_approval
from app.graph import prompts
from app.graph.context import RuntimeContext
from app.graph.state import AgentState
from app.tools.registry import ToolOutcome, ToolRegistry

log = get_logger(__name__)

MAX_TOOL_ROUNDS = 3


def tool_rounds(state: AgentState) -> int:
    return sum(1 for message in state.get("tool_messages", []) if isinstance(message, AIMessage))


def make_tool_agent(llm, registry: ToolRegistry):
    async def tool_agent(state: AgentState, runtime: Runtime[RuntimeContext]) -> dict:
        user = runtime.context
        tools = registry.tools_for(user.role)
        names = [tool.name for tool in tools]

        system = prompts.TOOL_AGENT.format(
            brand=get_settings().brand_name, name=user.name, role=user.role.value, tools=", ".join(names),
            locked=", ".join(registry.locked_for(user.role)) or "none",
            mcp_note="" if registry.mcp_available else prompts.MCP_DOWN_NOTE,
        )
        rejection = state.get("validation", {}).get("reason")
        if rejection:
            system += prompts.RETRY_FEEDBACK.format(reason=rejection)

        can_call_tools = tools and tool_rounds(state) < MAX_TOOL_ROUNDS
        model = llm.bind_tools([tool.spec() for tool in tools]) if can_call_tools else llm
        ai = await model.ainvoke([("system", system), *state["messages"][-6:], *state.get("tool_messages", [])])

        update = {"tool_messages": [ai], "tools_bound": names}
        if not ai.tool_calls:
            update |= {"draft": ai.text, "attempts": state.get("attempts", 0) + 1}
        return update

    return tool_agent


def route_after_tool_agent(state: AgentState) -> str:
    return "tool_executor" if state["tool_messages"][-1].tool_calls else "validator"


def ask_for_approval(calls: list[dict], role: Role) -> bool:
    risky = [call for call in calls if needs_approval(call["name"]) and can_use_tool(role, call["name"])]
    if not risky:
        return True
    decision = interrupt({
        "question": "The assistant wants to run an admin action. Approve?",
        "actions": [{"tool": call["name"], "args": call["args"]} for call in risky],
    })
    return bool(decision.get("approved"))


async def run_call(registry: ToolRegistry, call: dict, role: Role, approved: bool) -> ToolOutcome:
    if needs_approval(call["name"]) and can_use_tool(role, call["name"]) and not approved:
        return ToolOutcome("rejected", f"A human reviewer rejected '{call['name']}'. Do not retry it.")
    return await registry.execute(call["name"], call["args"], role)


def make_tool_executor(registry: ToolRegistry):
    async def tool_executor(state: AgentState, runtime: Runtime[RuntimeContext]) -> dict:
        role = runtime.context.role
        calls = state["tool_messages"][-1].tool_calls
        approved = ask_for_approval(calls, role)
        outcomes = await asyncio.gather(*[run_call(registry, call, role, approved) for call in calls])

        retrieved = list(state.get("retrieved", []))
        messages, results = [], []
        for call, outcome in zip(calls, outcomes, strict=True):
            messages.append(ToolMessage(content=outcome.content, tool_call_id=call["id"], name=call["name"]))
            results.append({"tool": call["name"], "args": call["args"], "status": outcome.status})
            if call["name"] == "knowledge_search" and outcome.status == "ok":
                retrieved.extend(outcome.data)

        log.info("tools_executed", results=[(r["tool"], r["status"]) for r in results])
        return {"tool_messages": messages, "tool_results": results, "retrieved": retrieved}

    return tool_executor
