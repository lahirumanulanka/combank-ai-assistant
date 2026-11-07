from langchain_core.messages import AIMessage
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

        if state["route"] == "chitchat":
            system = prompts.CHITCHAT.format(**details)
        elif not state.get("retrieved"):
            return {"messages": [AIMessage(content=prompts.NOT_FOUND)]}
        else:
            system = prompts.RESPONSE.format(**details, passages=format_passages(state["retrieved"]))

        answer = await llm.ainvoke([("system", system), *state["messages"][-6:]])
        return {"messages": [answer]}

    return response
