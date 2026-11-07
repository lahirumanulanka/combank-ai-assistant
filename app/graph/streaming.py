import json
from collections.abc import AsyncIterator

from langchain_core.messages import AIMessageChunk, HumanMessage

from app.graph.context import RuntimeContext


def sse(event: str, data: dict) -> str:
    return f"event: {event}\ndata: {json.dumps(data, default=str)}\n\n"


def summarize(node: str, update: dict) -> dict:
    if node == "supervisor":
        return {"route": update["route"], "rationale": update["rationale"], "search_query": update["search_query"]}
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


async def stream_events(graph, message: str, config: dict, context: RuntimeContext) -> AsyncIterator[str]:
    answer = ""
    async for mode, payload in graph.astream(
        {"messages": [HumanMessage(message)]},
        config=config,
        context=context,
        stream_mode=["updates", "messages"],
    ):
        if mode == "messages":
            chunk, metadata = payload
            if metadata.get("langgraph_node") == "response" and isinstance(chunk, AIMessageChunk) and chunk.text:
                yield sse("token", {"text": chunk.text})
        else:
            for node, update in payload.items():
                update = update or {}
                yield sse("node_end", {"node": node, **summarize(node, update)})
                if node == "validator" and update.get("messages"):
                    answer = update["messages"][-1].content

    yield sse("done", {"answer": answer})
