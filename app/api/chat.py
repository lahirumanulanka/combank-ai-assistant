import uuid

import structlog
from fastapi import APIRouter, Request
from fastapi.responses import StreamingResponse

from app.api.deps import RateLimitedUser
from app.api.schemas import ChatRequest
from app.core.errors import AssistantUnavailable
from app.core.logging import get_logger
from app.graph.context import RuntimeContext
from app.graph.streaming import sse, stream_events

log = get_logger(__name__)

router = APIRouter(prefix="/chat", tags=["chat"])

STREAM_HEADERS = {"Cache-Control": "no-cache", "X-Accel-Buffering": "no"}


@router.post("/stream")
async def chat_stream(body: ChatRequest, user: RateLimitedUser, request: Request) -> StreamingResponse:
    graph = request.app.state.graph
    if graph is None:
        raise AssistantUnavailable()

    thread_id = body.thread_id or uuid.uuid4().hex[:12]
    config = {"configurable": {"thread_id": f"{user.username}:{thread_id}"}}
    context = RuntimeContext(user_id=user.username, role=user.role, name=user.name)
    log_context = structlog.contextvars.get_contextvars()
    log.info("chat_started", thread_id=thread_id)

    async def events():
        structlog.contextvars.bind_contextvars(**log_context)
        yield sse("start", {"thread_id": thread_id})
        try:
            async for event in stream_events(graph, body.message, config, context):
                yield event
        except Exception:
            log.exception("chat_failed", thread_id=thread_id)
            yield sse("error", {"message": "Something went wrong while answering. Please try again."})

    return StreamingResponse(events(), media_type="text/event-stream", headers=STREAM_HEADERS)
