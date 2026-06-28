from __future__ import annotations

from functools import lru_cache
from typing import Literal

from pydantic import Field, computed_field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment variables and .env file."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # App
    app_name: str = "Library Intelligent Service"
    app_version: str = "0.1.0"
    app_env: Literal["development", "staging", "production", "test"] = "development"
    log_level: str = "INFO"
    trace_sample_ratio: float = 1.0  # 100% in dev; lower in prod

    # Database
    postgres_host: str = "localhost"
    postgres_port: int = 5432
    postgres_user: str = "library"
    postgres_db: str = "library"
    postgres_password: str = Field(default="dev_password", min_length=1)

    # Redis (placeholder for Plan 02)
    redis_url: str = "redis://localhost:6379/0"

    # JWT
    jwt_secret: str = Field(default="dev_secret_minimum_32_characters_long_xx", min_length=32)
    jwt_algorithm: str = "HS256"
    jwt_access_ttl_seconds: int = 3600
    jwt_refresh_ttl_seconds: int = 60 * 60 * 24 * 30  # 30 days

    # Default tenant
    default_tenant_code: str = "main_library"

    # CORS
    cors_origins: list[str] = ["http://localhost:5173", "http://localhost:8000"]

    # OTel
    otel_collector_endpoint: str = "http://localhost:4317"
    otel_service_name: str = "library-service"

    @computed_field  # type: ignore[prop-decorator]
    @property
    def database_url(self) -> str:
        """Async database URL for SQLAlchemy + asyncpg."""
        return (
            f"postgresql+asyncpg://{self.postgres_user}:{self.postgres_password}"
            f"@{self.postgres_host}:{self.postgres_port}/{self.postgres_db}"
        )

    @computed_field  # type: ignore[prop-decorator]
    @property
    def database_url_sync(self) -> str:
        """Sync database URL for Alembic."""
        return (
            f"postgresql://{self.postgres_user}:{self.postgres_password}"
            f"@{self.postgres_host}:{self.postgres_port}/{self.postgres_db}"
        )


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
