import uuid

import structlog
from fastapi import APIRouter, Request
from fastapi.responses import StreamingResponse

from app.api.deps import RateLimitedUser
from app.api.schemas import ChatRequest, ResumeRequest
from app.core.errors import ApprovalConflict, AssistantUnavailable, LLMUnavailable
from app.core.logging import get_logger
from app.core.users import User
from app.graph.context import RuntimeContext
from app.graph.streaming import human_decision, new_message, sse, stream_events

log = get_logger(__name__)

router = APIRouter(prefix="/chat", tags=["chat"])

STREAM_HEADERS = {"Cache-Control": "no-cache", "X-Accel-Buffering": "no"}


def get_graph(request: Request):
    graph = request.app.state.graph
    if graph is None:
        raise AssistantUnavailable()
    return graph


def thread_config(user: User, thread_id: str) -> dict:
    return {"configurable": {"thread_id": f"{user.username}:{thread_id}"}}


async def has_pending_approval(graph, config: dict) -> bool:
    snapshot = await graph.aget_state(config)
    return bool(snapshot.interrupts)


def event_stream(graph, graph_input, config: dict, user: User, thread_id: str) -> StreamingResponse:
    context = RuntimeContext(user_id=user.username, role=user.role, name=user.name)
    log_context = structlog.contextvars.get_contextvars()

    async def events():
        structlog.contextvars.bind_contextvars(**log_context)
        yield sse("start", {"thread_id": thread_id})
        try:
            async for event in stream_events(graph, graph_input, config, context):
                yield event
        except LLMUnavailable as exc:
            log.error("chat_llm_unavailable", thread_id=thread_id)
            yield sse("error", {"message": exc.message})
        except Exception:
            log.exception("chat_failed", thread_id=thread_id)
            yield sse("error", {"message": "Something went wrong while answering. Please try again."})

    return StreamingResponse(events(), media_type="text/event-stream", headers=STREAM_HEADERS)


@router.post("/stream")
async def chat_stream(body: ChatRequest, user: RateLimitedUser, request: Request) -> StreamingResponse:
    graph = get_graph(request)
    thread_id = body.thread_id or uuid.uuid4().hex[:12]
    config = thread_config(user, thread_id)
    if await has_pending_approval(graph, config):
        raise ApprovalConflict("An admin action is waiting for approval. Approve or reject it first.")

    log.info("chat_started", thread_id=thread_id)
    return event_stream(graph, new_message(body.message), config, user, thread_id)


@router.post("/resume")
async def chat_resume(body: ResumeRequest, user: RateLimitedUser, request: Request) -> StreamingResponse:
    graph = get_graph(request)
    config = thread_config(user, body.thread_id)
    if not await has_pending_approval(graph, config):
        raise ApprovalConflict("There is no action waiting for approval in this chat.")

    log.warning("human_decision", thread_id=body.thread_id, approved=body.approved)
    return event_stream(graph, human_decision(body.approved), config, user, body.thread_id)
