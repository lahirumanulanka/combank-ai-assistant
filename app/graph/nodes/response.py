from langgraph.runtime import Runtime

from app.core.config import get_settings
from app.graph import prompts
from app.graph.context import RuntimeContext
from app.graph.state import AgentState


def format_passages(retrieved: list[dict]) -> str:
    return "\n\n".join(
        f"[{chunk['chunk_id']}] ({chunk['title']} - {chunk['section']})\n{chunk['text']}" for chunk in retrieved
    )


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
            system = prompts.RESPONSE.format(**details, passages=format_passages(state["retrieved"]))
            rejection = state.get("validation", {}).get("reason")
            if rejection:
                system += prompts.RETRY_FEEDBACK.format(reason=rejection)

        answer = await llm.ainvoke([("system", system), *state["messages"][-6:]])
        return {"draft": answer.content, "attempts": attempts}

    return response
