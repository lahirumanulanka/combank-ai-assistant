from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


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


@lru_cache
def get_settings() -> Settings:
    return Settings()
