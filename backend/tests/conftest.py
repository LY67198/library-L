"""pytest 共享夹具 — 集成测试共用的 PostgreSQL 容器、Settings、DB engine/session、HTTPX Client 配置。"""
from __future__ import annotations

import asyncio
from collections.abc import AsyncGenerator
from typing import Any

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from testcontainers.postgres import PostgresContainer

from app.core.config import Settings, get_settings
from app.core.database import get_db_dependency
from app.main import create_app
from app.models import Base


@pytest.fixture(scope="session")
def event_loop() -> Any:
    """整个测试会话共享的 asyncio 事件循环。"""
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()


@pytest.fixture(scope="session")
def postgres_container() -> Any:
    """基于 testcontainers 启动的 PostgreSQL 15 容器,会话级共享。"""
    pg = PostgresContainer("postgres:15-alpine")
    pg.start()
    yield pg
    pg.stop()


@pytest.fixture(scope="session")
def test_settings(postgres_container: Any) -> Settings:
    """指向测试 PostgreSQL 容器、并在测试环境使用的 Settings 覆盖实例。"""
    url = postgres_container.get_connection_url()
    # Convert postgresql:// to postgresql+asyncpg://
    async_url = url.replace("postgresql://", "postgresql+asyncpg://", 1)
    sync_url = url

    settings = Settings(
        postgres_password=postgres_container.POSTGRES_PASSWORD,
        jwt_secret="test_secret_minimum_32_characters_long_xx",
        app_env="test",
        log_level="WARNING",
    )
    # Override URLs manually
    object.__setattr__(settings, "database_url", async_url)
    object.__setattr__(settings, "database_url_sync", sync_url)
    return settings


@pytest_asyncio.fixture(scope="session")
async def engine(test_settings: Settings) -> AsyncGenerator[AsyncEngine, None]:
    """基于测试数据库 URL 创建的 SQLAlchemy 异步引擎,启动时建表,会话结束释放。"""
    eng = create_async_engine(test_settings.database_url)
    async with eng.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield eng
    await eng.dispose()


@pytest_asyncio.fixture
async def db_session(engine: AsyncEngine) -> AsyncGenerator[AsyncSession, None]:
    """每个测试函数独立的 AsyncSession,函数结束回滚并清理除 tenants 之外的所有表。"""
    factory = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)
    async with factory() as session:
        yield session
        await session.rollback()
        # Clean tables between tests
        async with engine.begin() as conn:
            for table in reversed(Base.metadata.sorted_tables):
                if table.name != "tenants":
                    await conn.execute(table.delete())


@pytest_asyncio.fixture
async def client(
    test_settings: Settings, engine: AsyncEngine
) -> AsyncGenerator[AsyncClient, None]:
    """基于 ASGI 传输、覆写 get_db_dependency 的 HTTPX AsyncClient,用于调用 FastAPI。"""

    # Override get_settings:替换 lru_cache 包装的函数
    get_settings.cache_clear()

    from app.core import config as config_module

    config_module.get_settings = lambda: test_settings  # type: ignore[assignment]

    # Override get_db_dependency
    factory = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)

    async def override_get_db() -> AsyncGenerator[AsyncSession, None]:
        async with factory() as session:
            try:
                yield session
                await session.commit()
            except Exception:
                await session.rollback()
                raise

    app = create_app()
    app.dependency_overrides[get_db_dependency] = override_get_db

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        yield ac
