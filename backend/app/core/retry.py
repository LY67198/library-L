"""异步重试工具 — 提供带指数退避的 ``retry_async`` 函数及耗尽异常。
"""
from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable
from typing import TypeVar

T = TypeVar("T")


class RetryExhausted(Exception):
    """所有重试均失败后抛出,携带最后一次的异常与尝试次数。"""

    def __init__(self, last_exception: BaseException, attempts: int):
        """构造 RetryExhausted。

        参数:
            last_exception: 最后一次失败时的异常对象。
            attempts: 已执行的总尝试次数。
        """
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
    """以指数退避调用异步函数 ``fn``,失败后捕获 ``retry_on`` 指定的异常并重试。

    参数:
        fn: 零参异步可调用对象。
        max_attempts: 总尝试次数(1 表示不重试)。
        backoff_ms: 第 N 次重试前的睡眠毫秒数;默认 ``[100, 300, 900]``。
        retry_on: 需要触发重试的异常类型元组。

    返回值:
        T: ``fn`` 成功执行后的返回值。
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