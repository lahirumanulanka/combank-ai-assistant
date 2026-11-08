import os

from app.core.config import Settings


def configure_tracing(settings: Settings) -> bool:
    api_key = settings.langsmith_api_key.get_secret_value() if settings.langsmith_api_key else ""
    enabled = settings.langsmith_tracing and bool(api_key)

    os.environ["LANGSMITH_TRACING"] = "true" if enabled else "false"
    if enabled:
        os.environ["LANGSMITH_API_KEY"] = api_key
        os.environ["LANGSMITH_PROJECT"] = settings.langsmith_project
        os.environ["LANGSMITH_ENDPOINT"] = settings.langsmith_endpoint
    return enabled


def without_self(inputs: dict) -> dict:
    return {key: value for key, value in inputs.items() if key != "self"}


def as_documents(results: list) -> dict:
    return {
        "documents": [
            {
                "type": "Document",
                "page_content": result.text,
                "metadata": {"chunk_id": result.chunk_id, "score": result.score,
                             "access_level": result.access_level, "source": result.source},
            }
            for result in results
        ]
    }
