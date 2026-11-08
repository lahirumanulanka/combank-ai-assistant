from contextlib import asynccontextmanager

from fastapi import FastAPI
from langgraph.checkpoint.sqlite.aio import AsyncSqliteSaver
from langsmith import Client

from app.api import auth, chat, feedback, health
from app.api.error_handlers import install_error_handlers
from app.api.middleware import request_context_middleware
from app.core.config import MissingSetting, get_settings
from app.core.logging import configure_logging, get_logger
from app.core.runs import RunOwners
from app.core.tracing import configure_tracing
from app.graph.builder import build_default_graph

log = get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = get_settings()
    app.state.tracing = configure_tracing(settings)
    app.state.feedback_client = Client() if app.state.tracing else None
    log.info("tracing", langsmith=app.state.tracing, project=settings.langsmith_project if app.state.tracing else None)

    async with AsyncSqliteSaver.from_conn_string(settings.checkpoint_db) as checkpointer:
        try:
            app.state.graph = await build_default_graph(checkpointer)
            log.info("assistant_ready", model=settings.llm_strong)
        except (MissingSetting, FileNotFoundError) as exc:
            log.warning("assistant_disabled", reason=str(exc))
        yield


def create_app() -> FastAPI:
    settings = get_settings()
    configure_logging(settings.log_level, settings.log_json)

    app = FastAPI(title=settings.app_name, lifespan=lifespan)
    app.state.graph = None
    app.state.tracing = False
    app.state.feedback_client = None
    app.state.run_owners = RunOwners()
    app.middleware("http")(request_context_middleware)
    install_error_handlers(app)

    app.include_router(health.router)
    app.include_router(auth.router)
    app.include_router(chat.router)
    app.include_router(feedback.router)
    return app


app = create_app()
