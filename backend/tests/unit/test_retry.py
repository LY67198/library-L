"""重试机制测试 — 验证 retry_async 在首次成功、重试后成功、耗尽、未列入白名单异常下的行为。"""
import asyncio
import pytest

from app.core.retry import retry_async, RetryExhausted


async def test_retry_succeeds_first_try():
    """测试首次即成功:函数只被调用一次,直接返回结果,不会触发重试。"""
    calls = []

    async def fn():
        calls.append(1)
        return "ok"

    result = await retry_async(fn, max_attempts=3, backoff_ms=[1, 1, 1])
    assert result == "ok"
    assert len(calls) == 1


async def test_retry_then_succeed():
    """测试前两次失败第三次成功:函数被调用 3 次,最终返回 ok,符合 max_attempts 上限。"""
    calls = []

    async def fn():
        calls.append(1)
        if len(calls) < 3:
            raise ValueError("transient")
        return "ok"

    result = await retry_async(fn, max_attempts=3, backoff_ms=[1, 1, 1])
    assert result == "ok"
    assert len(calls) == 3


async def test_retry_exhausted_raises():
    """测试重试耗尽:函数始终抛 ValueError,达到 max_attempts 后抛出 RetryExhausted。"""
    async def fn():
        raise ValueError("nope")

    with pytest.raises(RetryExhausted):
        await retry_async(fn, max_attempts=3, backoff_ms=[1, 1, 1])


async def test_retry_only_catches_specific_exceptions():
    """测试异常白名单:不在 retry_on 中的异常(KeyError)应原样抛出,不被重试包装。"""
    async def fn():
        raise KeyError("nope")

    # KeyError not in retry_on -> raised immediately, not wrapped
    with pytest.raises(KeyError):
        await retry_async(fn, max_attempts=3, backoff_ms=[1, 1, 1], retry_on=(ValueError,))