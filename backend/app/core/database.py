"""数据库引擎与会话 — SQLAlchemy 异步引擎、Session 工厂与 FastAPI 依赖。
"""
from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from app.core.config import get_settings

_engine: AsyncEngine | None = None
_session_factory: async_sessionmaker[AsyncSession] | None = None


def init_engine() -> AsyncEngine:
    """初始化全局异步引擎与 Session 工厂(由应用 lifespan 调用)。

    返回值:
        AsyncEngine: 已创建的全局异步引擎;重复调用会直接返回现有实例。
    """
    global _engine, _session_factory
    if _engine is not None:
        return _engine
    settings = get_settings()
    _engine = create_async_engine(
        settings.database_url,
        echo=settings.app_env == "development",
        pool_pre_ping=True,
        pool_size=10,
        max_overflow=20,
    )
    _session_factory = async_sessionmaker(_engine, expire_on_commit=False, class_=AsyncSession)
    return _engine


async def dispose_engine() -> None:
    """关闭全局异步引擎,并清空引擎与 Session 工厂引用。

    返回值:
        None: 无返回值。
    """
    global _engine, _session_factory
    if _engine is not None:
        await _engine.dispose()
    _engine = None
    _session_factory = None


def get_session_factory() -> async_sessionmaker[AsyncSession]:
    """获取异步 Session 工厂;若尚未初始化则惰性触发初始化。

    返回值:
        async_sessionmaker[AsyncSession]: 可用于创建 AsyncSession 的工厂对象。
    """
    if _session_factory is None:
        init_engine()
    assert _session_factory is not None
    return _session_factory


@asynccontextmanager
async def get_db() -> AsyncIterator[AsyncSession]:
    """通用事务上下文管理器,产出 Session 并在退出时自动 commit / rollback。

    返回值:
        AsyncIterator[AsyncSession]: 异步迭代器,产出可用的 AsyncSession。
    """
    factory = get_session_factory()
    async with factory() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise


async def get_db_dependency() -> AsyncIterator[AsyncSession]:
    """FastAPI 依赖版本,每个请求产出独立 Session,成功提交 / 失败回滚。

    返回值:
        AsyncIterator[AsyncSession]: 异步迭代器,产出可用的 AsyncSession。
    """
    factory = get_session_factory()
    async with factory() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise