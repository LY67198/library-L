"""DistributedLock tests use fakeredis to avoid real Redis dependency."""
import asyncio
import pytest

from app.core.concurrency import LockAcquireError, DistributedLock


class FakeRedis:
    """Minimal Redis stub: SET NX PX, EVAL, GET, DELETE."""

    def __init__(self):
        self.store: dict[str, tuple[str, int]] = {}  # key -> (value, expire_ms)
        self.now_ms = 1_000_000

    async def set(self, key, value, nx=False, px=None):
        if nx and key in self.store:
            return None
        self.store[key] = (value, self.now_ms + (px or 0))
        return "OK"

    async def get(self, key):
        v = self.store.get(key)
        if v is None:
            return None
        if v[1] and v[1] < self.now_ms:
            del self.store[key]
            return None
        return v[0]

    async def eval(self, script, numkeys, key, token):
        # Release script: if GET == ARGV[1] then DEL
        v = await self.get(key)
        if v == token:
            del self.store[key]
            return 1
        return 0

    async def delete(self, key):
        if key in self.store:
            del self.store[key]


async def test_lock_acquire_release():
    r = FakeRedis()
    lock = DistributedLock(r, key="lock:1", ttl_ms=5000)
    await lock.__aenter__()
    assert await r.get("lock:1") is not None
    await lock.__aexit__(None, None, None)
    assert "lock:1" not in r.store


async def test_lock_already_held_raises():
    r = FakeRedis()
    await r.set("lock:1", "other-token", nx=True, px=5000)
    lock = DistributedLock(r, key="lock:1", ttl_ms=5000)
    with pytest.raises(LockAcquireError):
        await lock.__aenter__()


async def test_lock_only_holder_can_release():
    r = FakeRedis()
    # Holder A acquires
    lock_a = DistributedLock(r, key="lock:1", ttl_ms=5000)
    await lock_a.__aenter__()
    # Someone else overwrites the key directly
    await r.set("lock:1", "intruder", px=5000)
    # A's __aexit__ should NOT delete intruder's token
    await lock_a.__aexit__(None, None, None)
    assert await r.get("lock:1") == "intruder"
