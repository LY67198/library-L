"""Redis 异步客户端封装 — 提供全局单例的 Redis 连接管理。"""
from __future__ import annotations

from redis.asyncio import Redis, from_url

from app.core.config import get_settings

_redis: Redis | None = None


def init_redis() -> Redis:
    """初始化全局 Redis 客户端。在应用 lifespan 中调用。

    返回值:
        Redis: 全局复用的 Redis 异步连接实例。
    """
    global _redis
    if _redis is not None:
        return _redis
    settings = get_settings()
    _redis = from_url(
        settings.redis_url,
        encoding="utf-8",
        decode_responses=True,
        socket_connect_timeout=2.0,
        socket_timeout=2.0,
    )
    return _redis


async def dispose_redis() -> None:
    """关闭并释放全局 Redis 客户端。在应用 lifespan 关闭时调用。

    返回值:
        None: 无返回值。
    """
    global _redis
    if _redis is not None:
        await _redis.aclose()
    _redis = None


def get_redis() -> Redis:
    """获取全局 Redis 客户端。若未初始化则懒加载调用 init_redis。

    返回值:
        Redis: 全局复用的 Redis 异步连接实例。
    """
    if _redis is None:
        init_redis()
    assert _redis is not None
    return _redis