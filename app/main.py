from fastapi import FastAPI

from app.api import auth, health
from app.api.error_handlers import install_error_handlers
from app.api.middleware import request_context_middleware
from app.core.config import get_settings
from app.core.logging import configure_logging


def create_app() -> FastAPI:
    settings = get_settings()
    configure_logging(settings.log_level, settings.log_json)

    app = FastAPI(title=settings.app_name)
    app.middleware("http")(request_context_middleware)
    install_error_handlers(app)

    app.include_router(health.router)
    app.include_router(auth.router)
    return app


app = create_app()
