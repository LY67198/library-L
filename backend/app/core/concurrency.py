"""分布式锁 — 基于 Redis 的 ``SET NX PX`` + Lua 释放脚本,并提供带退避的重试辅助函数。
"""
from __future__ import annotations

import asyncio
import secrets
from collections.abc import Callable
from contextlib import AbstractAsyncContextManager
from typing import Any


class LockAcquireError(Exception):
    """无法获取分布式锁时抛出。"""


_RELEASE_SCRIPT = """
if redis.call('GET', KEYS[1]) == ARGV[1] then
    return redis.call('DEL', KEYS[1])
else
    return 0
end
"""


class DistributedLock(AbstractAsyncContextManager):
    """异步分布式锁(SET NX PX + Lua 安全释放)。

    使用方式::

        lock = DistributedLock(redis, key="seat:42", ttl_ms=3000)
        async with lock:
            ...
    """

    def __init__(self, redis: Any, *, key: str, ttl_ms: int):
        """构造分布式锁。

        参数:
            redis: 已连接的异步 Redis 客户端(支持 ``set`` / ``eval``)。
            key: 锁对应的 Redis Key。
            ttl_ms: 锁的过期毫秒数,防止持锁方崩溃后死锁。
        """
        self.redis = redis
        self.key = key
        self.ttl_ms = ttl_ms
        self.token = secrets.token_hex(16)
        self._held = False

    async def __aenter__(self) -> "DistributedLock":
        """尝试获取锁;若已被持有则抛出 ``LockAcquireError``。

        返回值:
            DistributedLock: 自身实例,供 ``async with`` 绑定。
        """
        ok = await self.redis.set(self.key, self.token, nx=True, px=self.ttl_ms)
        if not ok:
            raise LockAcquireError(f"Lock '{self.key}' is held by another holder")
        self._held = True
        return self

    async def __aexit__(self, exc_type, exc, tb) -> None:
        """退出上下文时通过 Lua 脚本原子释放锁(仅当 token 匹配)。"""
        if self._held:
            try:
                await self.redis.eval(_RELEASE_SCRIPT, 1, self.key, self.token)
            finally:
                self._held = False


async def acquire_with_retry(
    lock_factory: Callable[[], AbstractAsyncContextManager],
    *,
    max_retries: int = 3,
    backoff_ms: list[int] | None = None,
) -> AbstractAsyncContextManager:
    """以指数退避方式尝试获取锁,失败 ``max_retries`` 次后抛出 ``LockAcquireError``。

    参数:
        lock_factory: 每次重试都应返回一个新的锁上下文管理器的可调用对象。
        max_retries: 最大尝试次数(1 表示只尝试一次,不重试)。
        backoff_ms: 每次重试前的睡眠毫秒数;默认 ``[100, 200, 400]``。

    返回值:
        AbstractAsyncContextManager: 已成功进入的锁上下文管理器。
    """
    if backoff_ms is None:
        backoff_ms = [100, 200, 400]
    last_error: LockAcquireError | None = None
    for attempt in range(max_retries):
        lock = lock_factory()
        try:
            await lock.__aenter__()
            return lock
        except LockAcquireError as e:
            last_error = e
            if attempt < max_retries - 1:
                await asyncio.sleep(backoff_ms[min(attempt, len(backoff_ms) - 1)] / 1000)
    raise last_error or LockAcquireError("acquire_with_retry exhausted")