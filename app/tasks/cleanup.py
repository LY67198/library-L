"""Celery 任务：超时释放过期座位预约"""

from __future__ import annotations

import asyncio
from datetime import date

import redis.asyncio as aioredis

from core.cleanup import cleanup_expired_slots
from core.database import get_session_factory
from core.lock import SeatLock
from backend.config.settings import get_settings

from .celery_app import celery_app


@celery_app.task(name="tasks.cleanup.release_expired_slots")
def release_expired_slots() -> int:
    """Celery Beat 定时任务: 每 5 分钟清理当天所有过期的座位预约。"""

    async def _run():
        settings = get_settings()
        redis_client = aioredis.from_url(settings.redis_url, protocol=2)
        lock = SeatLock(redis_client)
        try:
            factory = get_session_factory()
            async with factory() as db:
                today = date.today()
                count = await cleanup_expired_slots(db, lock, today)
            return count
        finally:
            await redis_client.aclose()

    return asyncio.run(_run())
