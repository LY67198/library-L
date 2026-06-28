import asyncio
import pytest

from app.core.retry import retry_async, RetryExhausted


async def test_retry_succeeds_first_try():
    calls = []

    async def fn():
        calls.append(1)
        return "ok"

    result = await retry_async(fn, max_attempts=3, backoff_ms=[1, 1, 1])
    assert result == "ok"
    assert len(calls) == 1


async def test_retry_then_succeed():
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
    async def fn():
        raise ValueError("nope")

    with pytest.raises(RetryExhausted):
        await retry_async(fn, max_attempts=3, backoff_ms=[1, 1, 1])


async def test_retry_only_catches_specific_exceptions():
    async def fn():
        raise KeyError("nope")

    # KeyError not in retry_on -> raised immediately, not wrapped
    with pytest.raises(KeyError):
        await retry_async(fn, max_attempts=3, backoff_ms=[1, 1, 1], retry_on=(ValueError,))