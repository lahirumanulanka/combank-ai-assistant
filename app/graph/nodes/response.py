import json

from langgraph.runtime import Runtime

from app.core.config import get_settings
from app.graph import prompts
from app.graph.context import RuntimeContext
from app.graph.state import AgentState


def format_passages(retrieved: list[dict]) -> str:
    return "\n\n".join(
        f"<<doc id=\"{chunk['chunk_id']}\" title=\"{chunk['title']}\" section=\"{chunk['section']}\">>\n"
        f"{chunk['text']}\n<</doc>>"
        for chunk in retrieved
    )


def build_system_prompt(state: AgentState, details: dict) -> str:
    passages = format_passages(state["retrieved"])
    if state["route"] == "research":
        system = prompts.RESEARCH_RESPONSE.format(
            **details, analysis=json.dumps(state.get("analysis", {}), indent=1), passages=passages
        )
    else:
        system = prompts.RESPONSE.format(**details, passages=passages)

    if state.get("notice"):
        system += "\n\n" + state["notice"]
    if state.get("degraded"):
        system += prompts.DEGRADED_NOTE
    return system + prompts.SPOTLIGHT_RULE


def make_response(llm):
    async def response(state: AgentState, runtime: Runtime[RuntimeContext]) -> dict:
        user = runtime.context
        details = {"brand": get_settings().brand_name, "name": user.name, "role": user.role.value}
        attempts = state.get("attempts", 0) + 1

        if state["route"] == "chitchat":
            system = prompts.CHITCHAT.format(**details)
        elif not state.get("retrieved"):
            return {"draft": prompts.NOT_FOUND, "attempts": attempts}
        else:
            system = build_system_prompt(state, details)

        system += prompts.BRAND_RULES
        rejection = state.get("validation", {}).get("reason")
        if rejection:
            system += prompts.RETRY_FEEDBACK.format(reason=rejection)

        answer = await llm.ainvoke([("system", system), *state["messages"][-6:]])
        draft = answer.content
        if get_settings().chaos_fake_citation and attempts == 1 and state["route"] != "chitchat":
            draft += " [INC-1999-01-01#9]"
        return {"draft": draft, "attempts": attempts}

    return response
