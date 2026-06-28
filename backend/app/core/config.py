"""应用配置 — 基于环境变量与 .env 文件加载的全局设置。
"""
from __future__ import annotations

from functools import lru_cache
from typing import Literal

from pydantic import Field, computed_field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """应用配置类,从环境变量与 .env 文件加载,并提供衍生字段(如数据库 URL)。"""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # 应用基础信息
    app_name: str = "Library Intelligent Service"
    app_version: str = "0.1.0"
    app_env: Literal["development", "staging", "production", "test"] = "development"
    log_level: str = "INFO"
    trace_sample_ratio: float = 1.0  # 开发环境采样率 100%;生产环境应调低

    # 数据库(PostgreSQL)
    postgres_host: str = "localhost"
    postgres_port: int = 5432
    postgres_user: str = "library"
    postgres_db: str = "library"
    postgres_password: str = Field(default="dev_password", min_length=1)

    # Redis(Plan 02 进一步使用)
    redis_url: str = "redis://localhost:6379/0"

    # JWT 配置
    jwt_secret: str = Field(default="dev_secret_minimum_32_characters_long_xx", min_length=32)
    jwt_algorithm: str = "HS256"
    jwt_access_ttl_seconds: int = 3600
    jwt_refresh_ttl_seconds: int = 60 * 60 * 24 * 30  # 30 天

    # 默认租户
    default_tenant_code: str = "main_library"

    # CORS 允许的来源
    cors_origins: list[str] = ["http://localhost:5173", "http://localhost:8000"]

    # 外部 API
    dashscope_api_key: str = Field(default="sk-placeholder", min_length=1)

    # OpenTelemetry
    otel_collector_endpoint: str = "http://localhost:4317"
    otel_service_name: str = "library-service"

    @computed_field  # type: ignore[prop-decorator]
    @property
    def database_url(self) -> str:
        """异步数据库连接 URL,供 SQLAlchemy + asyncpg 使用。

        返回值:
            str: postgresql+asyncpg 格式的 DSN。
        """
        return (
            f"postgresql+asyncpg://{self.postgres_user}:{self.postgres_password}"
            f"@{self.postgres_host}:{self.postgres_port}/{self.postgres_db}"
        )

    @computed_field  # type: ignore[prop-decorator]
    @property
    def database_url_sync(self) -> str:
        """同步数据库连接 URL,供 Alembic 迁移使用。

        返回值:
            str: postgresql 格式的 DSN。
        """
        return (
            f"postgresql://{self.postgres_user}:{self.postgres_password}"
            f"@{self.postgres_host}:{self.postgres_port}/{self.postgres_db}"
        )


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """获取全局缓存的 Settings 实例(进程级单例)。

    返回值:
        Settings: 已加载并缓存的配置对象。
    """
    return Settings()