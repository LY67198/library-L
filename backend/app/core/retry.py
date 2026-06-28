"""Async retry with exponential backoff."""
from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable
from typing import TypeVar

T = TypeVar("T")


class RetryExhausted(Exception):
    """Raised when all retry attempts fail."""

    def __init__(self, last_exception: BaseException, attempts: int):
        super().__init__(f"Retry exhausted after {attempts} attempts: {last_exception!r}")
        self.last_exception = last_exception
        self.attempts = attempts


async def retry_async(
    fn: Callable[[], Awaitable[T]],
    *,
    max_attempts: int = 3,
    backoff_ms: list[int] | None = None,
    retry_on: tuple[type[BaseException], ...] = (Exception,),
) -> T:
    """Call `fn` with exponential-backoff retry.

    Args:
        fn: zero-arg async callable
        max_attempts: total attempts (1 = no retry)
        backoff_ms: sleep BEFORE retry #N; default [100, 300, 900]
        retry_on: exception types to catch & retry
    """
    if backoff_ms is None:
        backoff_ms = [100, 300, 900]
    last_exc: BaseException | None = None
    for attempt in range(1, max_attempts + 1):
        try:
            return await fn()
        except retry_on as e:
            last_exc = e
            if attempt < max_attempts:
                idx = min(attempt - 1, len(backoff_ms) - 1)
                await asyncio.sleep(backoff_ms[idx] / 1000)
    assert last_exc is not None
    raise RetryExhausted(last_exc, max_attempts)