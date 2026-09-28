"""
Central application configuration.

Loaded from environment variables (see .env.example). Never hard-code
secrets here — this module only defines defaults for local development.
"""
from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    app_env: str = "local"
    log_level: str = "INFO"

    database_url: str = "postgresql+asyncpg://expense_user:expense_pw@localhost:5432/expense_gateway"
    redis_url: str = "redis://localhost:6379/0"

    jwt_secret_key: str = "dev-only-change-me"
    jwt_algorithm: str = "HS256"
    jwt_access_token_expire_minutes: int = 30

    mtls_ca_cert_path: str = "certs/ca/ca.crt"
    mtls_server_cert_path: str = "certs/server/server.crt"
    mtls_server_key_path: str = "certs/server/server.key"

    correlation_id_header: str = "X-Correlation-Id"

    integration_max_retries: int = 3
    integration_backoff_base_seconds: float = 1.0


@lru_cache
def get_settings() -> Settings:
    return Settings()
