import time
import uuid

import structlog
from fastapi import Request

from app.core.logging import get_logger

log = get_logger(__name__)

REQUEST_ID_HEADER = "X-Request-ID"


async def request_context_middleware(request: Request, call_next):
    request_id = request.headers.get(REQUEST_ID_HEADER) or uuid.uuid4().hex[:12]

    structlog.contextvars.clear_contextvars()
    structlog.contextvars.bind_contextvars(
        request_id=request_id,
        method=request.method,
        path=request.url.path,
    )

    started = time.perf_counter()
    response = await call_next(request)
    duration_ms = round((time.perf_counter() - started) * 1000, 1)

    if not (request.url.path == "/health" and response.status_code == 200):
        log.info("request_finished", status=response.status_code, duration_ms=duration_ms)
    response.headers[REQUEST_ID_HEADER] = request_id
    return response
