from langchain.chat_models import init_chat_model
from langchain_core.language_models import BaseChatModel
from langgraph.config import get_stream_writer

from app.core.config import Settings, require_secret
from app.core.errors import LLMUnavailable
from app.core.logging import get_logger

log = get_logger(__name__)

API_KEY_ENV = {"anthropic": "ANTHROPIC_API_KEY", "openai": "OPENAI_API_KEY"}


def create_chat_model(model: str, settings: Settings) -> BaseChatModel:
    provider = model.split(":", 1)[0]
    if provider not in API_KEY_ENV:
        raise ValueError(f"Unsupported LLM provider '{provider}'. Use one of: {', '.join(API_KEY_ENV)}")

    secret = settings.anthropic_api_key if provider == "anthropic" else settings.openai_api_key
    api_key = require_secret(secret, API_KEY_ENV[provider])
    return init_chat_model(model, api_key=api_key, timeout=settings.llm_timeout_s, max_retries=2)


class BrokenModel:
    """Stands in for the main model when CHAOS_LLM_FAIL is on."""

    async def ainvoke(self, messages, **kwargs):
        raise ConnectionError("chaos: primary LLM is down")

    def with_structured_output(self, schema):
        return self

    def bind_tools(self, tools):
        return self


def tell_activity_panel(event: dict) -> None:
    try:
        get_stream_writer()(event)
    except RuntimeError:
        pass


class FallbackModel:
    def __init__(self, primary, fallback, fallback_name: str):
        self.primary = primary
        self.fallback = fallback
        self.fallback_name = fallback_name

    async def ainvoke(self, messages, **kwargs):
        try:
            return await self.primary.ainvoke(messages, **kwargs)
        except Exception as exc:
            log.warning("llm_primary_failed", error=type(exc).__name__, fallback=self.fallback_name or None)
            if self.fallback is None:
                raise LLMUnavailable() from exc
            tell_activity_panel({"type": "llm_fallback", "error": type(exc).__name__, "model": self.fallback_name})
        try:
            return await self.fallback.ainvoke(messages, **kwargs)
        except Exception as exc:
            log.error("llm_fallback_failed", error=type(exc).__name__)
            raise LLMUnavailable() from exc

    def with_structured_output(self, schema):
        fallback = self.fallback.with_structured_output(schema) if self.fallback else None
        return FallbackModel(self.primary.with_structured_output(schema), fallback, self.fallback_name)

    def bind_tools(self, tools):
        fallback = self.fallback.bind_tools(tools) if self.fallback else None
        return FallbackModel(self.primary.bind_tools(tools), fallback, self.fallback_name)


def create_resilient_model(model: str, settings: Settings) -> FallbackModel:
    primary = BrokenModel() if settings.chaos_llm_fail else create_chat_model(model, settings)
    fallback = create_chat_model(settings.llm_fallback, settings) if settings.llm_fallback else None
    return FallbackModel(primary, fallback, settings.llm_fallback)
