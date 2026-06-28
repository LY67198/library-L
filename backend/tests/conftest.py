from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator
from typing import Any

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from testcontainers.postgres import PostgresContainer

from app.core.config import Settings, get_settings
from app.core.database import get_db_dependency
from app.main import create_app
from app.models import Base


@pytest.fixture(scope="session")
def event_loop():
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()


@pytest.fixture(scope="session")
def postgres_container() -> Any:
    pg = PostgresContainer("postgres:15-alpine")
    pg.start()
    yield pg
    pg.stop()


@pytest.fixture(scope="session")
def test_settings(postgres_container: Any) -> Settings:
    """Settings override pointing to the test PostgreSQL container."""
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
async def engine(test_settings: Settings):
    eng = create_async_engine(test_settings.database_url)
    async with eng.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield eng
    await eng.dispose()


@pytest_asyncio.fixture
async def db_session(engine) -> AsyncIterator[AsyncSession]:
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
async def client(test_settings: Settings, engine) -> AsyncIterator[AsyncClient]:
    """HTTPX client with overridden DB session."""

    # Override get_settings
    get_settings.cache_clear()

    from app.core import config as config_module
    config_module.get_settings = lambda: test_settings

    # Override get_db_dependency
    factory = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)

    async def override_get_db():
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
