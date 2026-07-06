"""Redis 分布式锁 — 座位预约并发控制"""

from __future__ import annotations

import redis.asyncio as aioredis


class SeatLock:
    """座位预约分布式锁。仅用于预约操作窗口的快速抢占，持久状态靠 PG。"""

    def __init__(self, redis_client: aioredis.Redis):
        self._redis = redis_client

    async def acquire(
        self, seat_id: str, date: str, slot: str, user_id: str, ttl: int = 30
    ) -> bool:
        """返回 True 表示抢锁成功"""
        key = f"seat:{seat_id}:{date}:{slot}"
        result = await self._redis.set(key, user_id, nx=True, ex=ttl)
        return result is not None

    async def release(self, seat_id: str, date: str, slot: str) -> None:
        """释放锁"""
        key = f"seat:{seat_id}:{date}:{slot}"
        await self._redis.delete(key)

    async def is_locked(self, seat_id: str, date: str, slot: str) -> bool:
        """检查是否被锁定"""
        key = f"seat:{seat_id}:{date}:{slot}"
        return await self._redis.exists(key) > 0
