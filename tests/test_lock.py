"""Redis 分布式锁单元测试 — 使用 fakeredis"""

import pytest
import pytest_asyncio
from core.lock import SeatLock


@pytest_asyncio.fixture
async def redis_client():
    import fakeredis.aioredis

    client = fakeredis.aioredis.FakeRedis()
    yield client
    await client.aclose()


@pytest_asyncio.fixture
async def lock(redis_client):
    return SeatLock(redis_client)


@pytest.mark.asyncio
async def test_acquire_success(lock):
    ok = await lock.acquire("seat-1", "2026-07-06", "morning", "user-1")
    assert ok is True


@pytest.mark.asyncio
async def test_acquire_duplicate_fails(lock):
    ok1 = await lock.acquire("seat-1", "2026-07-06", "morning", "user-1")
    ok2 = await lock.acquire("seat-1", "2026-07-06", "morning", "user-2")
    assert ok1 is True
    assert ok2 is False


@pytest.mark.asyncio
async def test_acquire_different_seat_succeeds(lock):
    ok1 = await lock.acquire("seat-1", "2026-07-06", "morning", "user-1")
    ok2 = await lock.acquire("seat-2", "2026-07-06", "morning", "user-2")
    assert ok1 is True
    assert ok2 is True


@pytest.mark.asyncio
async def test_release_then_reacquire(lock):
    await lock.acquire("seat-1", "2026-07-06", "morning", "user-1")
    await lock.release("seat-1", "2026-07-06", "morning")
    ok = await lock.acquire("seat-1", "2026-07-06", "morning", "user-2")
    assert ok is True


@pytest.mark.asyncio
async def test_is_locked(lock):
    await lock.acquire("seat-1", "2026-07-06", "morning", "user-1")
    assert await lock.is_locked("seat-1", "2026-07-06", "morning") is True
    assert await lock.is_locked("seat-2", "2026-07-06", "morning") is False
