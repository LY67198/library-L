"""Async Redis client wrapper."""
from __future__ import annotations

from redis.asyncio import Redis, from_url

from app.core.config import get_settings

_redis: Redis | None = None


def init_redis() -> Redis:
    """Initialize global Redis client. Called from app lifespan."""
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
    global _redis
    if _redis is not None:
        await _redis.aclose()
    _redis = None


def get_redis() -> Redis:
    if _redis is None:
        init_redis()
    assert _redis is not None
    return _redis