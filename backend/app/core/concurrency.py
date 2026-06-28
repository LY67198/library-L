"""Distributed lock with Lua release + retry helpers."""
from __future__ import annotations

import asyncio
import secrets
from collections.abc import Awaitable, Callable
from contextlib import AbstractAsyncContextManager
from typing import Any, TypeVar

T = TypeVar("T")


class LockAcquireError(Exception):
    """Raised when a distributed lock cannot be acquired."""


_RELEASE_SCRIPT = """
if redis.call('GET', KEYS[1]) == ARGV[1] then
    return redis.call('DEL', KEYS[1])
else
    return 0
end
"""


class DistributedLock(AbstractAsyncContextManager):
    """Async distributed lock (SET NX PX + Lua release).

    Usage:
        lock = DistributedLock(redis, key="seat:42", ttl_ms=3000)
        async with lock:
            ...
    """

    def __init__(self, redis: Any, *, key: str, ttl_ms: int):
        self.redis = redis
        self.key = key
        self.ttl_ms = ttl_ms
        self.token = secrets.token_hex(16)
        self._held = False

    async def __aenter__(self) -> "DistributedLock":
        ok = await self.redis.set(self.key, self.token, nx=True, px=self.ttl_ms)
        if not ok:
            raise LockAcquireError(f"Lock '{self.key}' is held by another holder")
        self._held = True
        return self

    async def __aexit__(self, exc_type, exc, tb) -> None:
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
    """Acquire a lock with exponential backoff. Raises LockAcquireError after max_retries.

    Args:
        lock_factory: callable returning a new lock context manager each attempt
        max_retries: total attempts (1 = try once, no retry)
        backoff_ms: sleep before each retry; default [100, 200, 400]
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
