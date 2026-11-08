from functools import lru_cache

from pydantic import Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class MissingSetting(Exception):
    pass


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    app_name: str = "Commercial Bank Knowledge Assistant"
    brand_name: str = "Commercial Bank"
    log_level: str = "INFO"
    log_json: bool = False

    jwt_secret: str
    jwt_algorithm: str = "HS256"
    jwt_ttl_s: int = 7200
    users_file: str = "data/users.yaml"

    rate_limit_viewer: tuple[float, float] = (10, 0.2)
    rate_limit_analyst: tuple[float, float] = (20, 0.5)
    rate_limit_admin: tuple[float, float] = (30, 1.0)

    docs_dir: str = "data/docs"
    bm25_params_path: str = "data/bm25_params.json"

    openai_api_key: SecretStr | None = None
    embedding_model: str = "text-embedding-3-small"
    embedding_dimension: int = 1536

    pinecone_api_key: SecretStr | None = None
    pinecone_index: str = "combank-kb"
    pinecone_cloud: str = "aws"
    pinecone_region: str = "us-east-1"

    hybrid_alpha: float = Field(0.7, ge=0, le=1)
    retrieval_top_k: int = 8
    retrieval_min_score: float = 0.3

    anthropic_api_key: SecretStr | None = None
    llm_strong: str = "anthropic:claude-sonnet-5-5"
    llm_cheap: str = "anthropic:claude-haiku-5-5"
    llm_fallback: str = ""
    llm_timeout_s: float = 40

    checkpoint_db: str = "data/checkpoints.db"

    mcp_url: str = "http://localhost:8001/mcp"
    mcp_timeout_s: float = 5
    tool_timeout_s: float = 10

    pinecone_timeout_s: float = 5
    breaker_failures: int = 3
    breaker_cooldown_s: float = 30

    langsmith_tracing: bool = True
    langsmith_api_key: SecretStr | None = None
    langsmith_project: str = "commbank-assistant"
    langsmith_endpoint: str = "https://api.smith.langchain.com"

    chaos_llm_fail: bool = False
    chaos_pinecone_fail: bool = False
    chaos_mcp_down: bool = False
    chaos_tool_slow_ms: int = 0
    chaos_fake_citation: bool = False


def require_secret(value: SecretStr | None, env_name: str) -> str:
    if value is None or not value.get_secret_value():
        raise MissingSetting(f"{env_name} is not set. Add it to your .env file.")
    return value.get_secret_value()


@lru_cache
def get_settings() -> Settings:
    return Settings()
