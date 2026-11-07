from langchain.chat_models import init_chat_model
from langchain_core.language_models import BaseChatModel

from app.core.config import Settings, require_secret

API_KEY_ENV = {"anthropic": "ANTHROPIC_API_KEY", "openai": "OPENAI_API_KEY"}


def create_chat_model(model: str, settings: Settings) -> BaseChatModel:
    provider = model.split(":", 1)[0]
    if provider not in API_KEY_ENV:
        raise ValueError(f"Unsupported LLM provider '{provider}'. Use one of: {', '.join(API_KEY_ENV)}")

    secret = settings.anthropic_api_key if provider == "anthropic" else settings.openai_api_key
    api_key = require_secret(secret, API_KEY_ENV[provider])
    return init_chat_model(model, api_key=api_key, timeout=settings.llm_timeout_s, max_retries=2)
