import json
from collections.abc import AsyncIterator

from langchain_core.messages import AIMessageChunk, HumanMessage
from langgraph.types import Command

from app.graph.context import RuntimeContext

ANSWER_NODES = {"response", "tool_agent"}


def sse(event: str, data: dict) -> str:
    return f"event: {event}\ndata: {json.dumps(data, default=str)}\n\n"


def summarize(node: str, update: dict) -> dict:
    if node == "supervisor":
        return {"route": update["route"], "rationale": update["rationale"],
                "search_query": update["search_query"], "downgraded": bool(update.get("notice"))}
    if node == "research_plan":
        return {"code": update["plan_code"], "rationale": update["plan_rationale"]}
    if node == "research_execute":
        return {"source": update["plan_source"], "batches": update["batches"]}
    if node == "research_worker":
        return {"analysed": [finding["incident_id"] for finding in update.get("findings", [])],
                "errors": update.get("research_errors", [])}
    if node == "research_aggregate":
        analysis = update["analysis"]
        return {"coverage": analysis["coverage"], "period": analysis["period"],
                "excluded": analysis["excluded"], "root_causes": analysis["root_causes"]}
    if node == "tool_agent":
        calls = update["tool_messages"][-1].tool_calls
        return {"tools": update["tools_bound"],
                "calls": [{"name": call["name"], "args": call["args"]} for call in calls]}
    if node == "tool_executor":
        return {"results": update["tool_results"]}
    if node == "retrieval":
        chunk_ids = [chunk["chunk_id"] for chunk in update["retrieved"]]
        return {"found": len(chunk_ids), "chunk_ids": chunk_ids}
    if node == "response":
        return {"attempt": update["attempts"]}
    if node == "validator":
        validation = update["validation"]
        return {
            "ok": validation.get("ok", False),
            "cited": validation.get("cited", []),
            "unknown": validation.get("unknown", []),
            "reason": validation.get("reason", ""),
        }
    return {}


def new_message(message: str) -> dict:
    return {"messages": [HumanMessage(message)]}


def human_decision(approved: bool) -> Command:
    return Command(resume={"approved": approved})


async def stream_events(graph, graph_input, config: dict, context: RuntimeContext) -> AsyncIterator[str]:
    answer, waiting = "", False
    async for mode, payload in graph.astream(
        graph_input,
        config=config,
        context=context,
        stream_mode=["updates", "messages"],
    ):
        if mode == "messages":
            chunk, metadata = payload
            if metadata.get("langgraph_node") in ANSWER_NODES and isinstance(chunk, AIMessageChunk) and chunk.text:
                yield sse("token", {"text": chunk.text})
            continue

        for node, update in payload.items():
            if node == "__interrupt__":
                waiting = True
                yield sse("interrupt", update[0].value)
                continue
            update = update or {}
            yield sse("node_end", {"node": node, **summarize(node, update)})
            if node == "validator" and update.get("messages"):
                answer = update["messages"][-1].content

    yield sse("done", {"answer": answer, "awaiting_approval": waiting})
