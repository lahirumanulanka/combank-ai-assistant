import structlog
from fastapi import FastAPI, Request
from fastapi.encoders import jsonable_encoder
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.core.errors import AppError
from app.core.logging import get_logger

log = get_logger(__name__)


def _error_response(status_code: int, code: str, message: str, extra: dict | None = None,
                    headers: dict | None = None) -> JSONResponse:
    request_id = structlog.contextvars.get_contextvars().get("request_id")
    body = {"error": code, "message": message, **(extra or {}), "request_id": request_id}
    return JSONResponse(status_code=status_code, content=jsonable_encoder(body), headers=headers)


async def handle_app_error(request: Request, exc: AppError) -> JSONResponse:
    log.warning("app_error", code=exc.code, message=exc.message)
    return _error_response(exc.status_code, exc.code, exc.message, exc.extra, exc.headers)


async def handle_validation_error(request: Request, exc: RequestValidationError) -> JSONResponse:
    log.warning("invalid_request", errors=len(exc.errors()))
    return _error_response(422, "invalid_request", "The request is not valid.", {"details": exc.errors()})


async def handle_http_error(request: Request, exc: StarletteHTTPException) -> JSONResponse:
    return _error_response(exc.status_code, "http_error", str(exc.detail), headers=exc.headers)


async def handle_unexpected_error(request: Request, exc: Exception) -> JSONResponse:
    log.exception("unexpected_error")
    return _error_response(500, "internal_error", "Something went wrong. Please try again.")


def install_error_handlers(app: FastAPI) -> None:
    app.add_exception_handler(AppError, handle_app_error)
    app.add_exception_handler(RequestValidationError, handle_validation_error)
    app.add_exception_handler(StarletteHTTPException, handle_http_error)
    app.add_exception_handler(Exception, handle_unexpected_error)
