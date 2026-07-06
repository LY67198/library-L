# Phase 2c: Celery 超时释放 — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 引入 Celery Beat 定时任务，每 5 分钟主动扫描并释放过期座位预约。

**Architecture:** 清理逻辑抽离到 `app/core/cleanup.py`，Celery 任务和 SeatService 懒清理共用。Celery 用 Redis 做 broker（复用现有 `REDIS_URL`），Beat 做调度。

**Tech Stack:** Celery 5.x + Redis broker + fakeredis (test) + aiosqlite (test)

---

### Task 1: 添加 Celery 依赖

**Files:**
- Modify: `pyproject.toml`

- [ ] **Step 1: 添加 celery[redis] 依赖**

```toml
# pyproject.toml — dependencies 列表追加
"celery[redis]>=5.4",
```

完整 dependencies 块：
```toml
dependencies = [
  "fastapi>=0.115.0",
  "uvicorn[standard]>=0.30.0",
  "pydantic>=2.8.0",
  "pydantic-settings>=2.4.0",
  "langgraph>=1.2.0",
  "sqlalchemy[asyncio]>=2.0",
  "asyncpg>=0.30",
  "alembic>=1.14",
  "python-jose[cryptography]>=3.3",
  "bcrypt>=4.0",
  "redis[hiredis]>=5.0",
  "celery[redis]>=5.4",
]
```

- [ ] **Step 2: 安装依赖**

```bash
cd deep_research_scaffold && uv sync
```

- [ ] **Step 3: 验证 Celery 可导入**

```bash
cd deep_research_scaffold && uv run python -c "import celery; print(celery.__version__)"
```

- [ ] **Step 4: Commit**

```bash
cd deep_research_scaffold && git add pyproject.toml uv.lock && git commit -m "feat(phase2c): add celery[redis] dependency"
```

---

### Task 2: 抽离公共清理逻辑 — `app/core/cleanup.py`

**Files:**
- Create: `app/core/cleanup.py`
- Modify: `app/core/__init__.py`（不存在则创建）

- [ ] **Step 1: 创建 `app/core/cleanup.py`**

```python
"""座位预约超时清理 — Celery 与懒清理共用"""

from __future__ import annotations

from datetime import date, datetime, time, timezone

from sqlalchemy import and_, select
from sqlalchemy.ext.asyncio import AsyncSession

from models import Appointment, AppointmentStatus, SeatTimeSlot, TimeSlot

SLOT_TIMES: dict[str, tuple[time, time]] = {
    "morning": (time(8, 0), time(12, 0)),
    "afternoon": (time(13, 0), time(17, 0)),
    "evening": (time(18, 0), time(22, 0)),
}


def _slot_cutoff(date_value: date, slot: str) -> datetime:
    """计算某时段过期截止时间：slot_start + 30min"""
    slot_start, _ = SLOT_TIMES[slot]
    slot_start_dt = datetime.combine(date_value, slot_start, tzinfo=timezone.utc)
    return slot_start_dt.replace(minute=slot_start_dt.minute + 30)


async def cleanup_expired_slots(
    db: AsyncSession,
    lock,  # SeatLock
    date_value: date,
    slot: str | None = None,
) -> int:
    """清理过期未签到的预约。slot=None 则清理所有时段。返回清理条数。"""
    slots_to_check = [slot] if slot else list(SLOT_TIMES.keys())
    now = datetime.now(timezone.utc)
    cleaned = 0

    for s in slots_to_check:
        cutoff = _slot_cutoff(date_value, s)
        if now < cutoff:
            continue

        result = await db.execute(
            select(SeatTimeSlot).join(Appointment).where(
                and_(
                    SeatTimeSlot.date == date_value,
                    SeatTimeSlot.slot == TimeSlot(s),
                    Appointment.status == AppointmentStatus.booked,
                    SeatTimeSlot.booked_at < cutoff,
                )
            )
        )
        expired_sts = result.scalars().all()

        for sts in expired_sts:
            await lock.release(sts.seat_id, str(date_value), s)
            await db.delete(sts)

        if expired_sts:
            appt_result = await db.execute(
                select(Appointment).where(
                    and_(
                        Appointment.seat_id.in_([sts.seat_id for sts in expired_sts]),
                        Appointment.date == date_value,
                        Appointment.slot == TimeSlot(s),
                        Appointment.status == AppointmentStatus.booked,
                    )
                )
            )
            for appt in appt_result.scalars().all():
                appt.status = AppointmentStatus.expired

        cleaned += len(expired_sts)

    if cleaned:
        await db.commit()
    return cleaned
```

- [ ] **Step 2: 创建 `app/core/__init__.py`**

```python
"""核心基础设施"""
```

- [ ] **Step 3: Commit**

```bash
cd deep_research_scaffold && git add app/core/cleanup.py app/core/__init__.py && git commit -m "feat(phase2c): extract shared cleanup logic to app/core/cleanup.py"
```

---

### Task 3: 创建 Celery 应用实例

**Files:**
- Create: `app/tasks/__init__.py`
- Create: `app/tasks/celery_app.py`

- [ ] **Step 1: 创建 `app/tasks/__init__.py`**

```python
"""Celery 异步任务包"""
```

- [ ] **Step 2: 创建 `app/tasks/celery_app.py`**

```python
"""Celery 应用实例 + Beat 调度配置"""

from __future__ import annotations

from celery import Celery
from celery.schedules import crontab

from backend.config.settings import get_settings

settings = get_settings()

celery_app = Celery(
    "library",
    broker=settings.redis_url,
    broker_connection_retry_on_startup=True,
)

celery_app.conf.timezone = "UTC"
celery_app.conf.beat_schedule = {
    "release-expired-slots": {
        "task": "tasks.cleanup.release_expired_slots",
        "schedule": crontab(minute="*/5"),
    },
}
```

- [ ] **Step 3: 验证 Celery app 能正常加载**

```bash
cd deep_research_scaffold/app && uv run python -c "from tasks.celery_app import celery_app; print(celery_app.conf.broker_url)"
```

应输出 broker URL（如 `redis://localhost:6379/0`）。

- [ ] **Step 4: Commit**

```bash
cd deep_research_scaffold && git add app/tasks/__init__.py app/tasks/celery_app.py && git commit -m "feat(phase2c): create Celery app with Beat schedule"
```

---

### Task 4: 创建 Celery 清理任务

**Files:**
- Create: `app/tasks/cleanup.py`

- [ ] **Step 1: 创建 `app/tasks/cleanup.py`**

```python
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
```

- [ ] **Step 2: 提交**

```bash
cd deep_research_scaffold && git add app/tasks/cleanup.py && git commit -m "feat(phase2c): create Celery cleanup task"
```

---

### Task 5: SeatService 懒清理改用公共函数

**Files:**
- Modify: `app/backend/service/seat_service.py`

- [ ] **Step 1: 修改 `_cleanup_expired_slots` 方法**

将文件开头的 imports 替换/追加：

在文件顶部 import 区新增：
```python
from core.cleanup import cleanup_expired_slots as _do_cleanup
```

将 `_cleanup_expired_slots` 方法替换为：

```python
    async def _cleanup_expired_slots(self, date_value: Date, slot: str) -> None:
        """懒清理：释放过期未签到的预约。委托 core.cleanup。"""
        await _do_cleanup(self._db, self._lock, date_value, slot)
```

同时删除旧的 `SLOT_TIMES` 常量（它现在定义在 `core/cleanup.py` 中）。

变更后 `seat_service.py` 开头的 import 区应为：

```python
"""座位预约业务逻辑"""

from __future__ import annotations

from datetime import date as Date, datetime, timezone

from sqlalchemy import and_, select
from sqlalchemy.ext.asyncio import AsyncSession

from core.cleanup import cleanup_expired_slots as _do_cleanup
from core.lock import SeatLock
from models import (
    Appointment,
    AppointmentStatus,
    Floor,
    Seat,
    SeatStatus,
    SeatTimeSlot,
    TimeSlot,
    Zone,
)
```

删除原有的 `SLOT_TIMES` 常量（约第 22-26 行）。

- [ ] **Step 2: 运行现有测试确保不破坏**

```bash
cd deep_research_scaffold && uv run pytest tests/ -v
```

预期：所有 57 tests passed。

- [ ] **Step 3: Commit**

```bash
cd deep_research_scaffold && git add app/backend/service/seat_service.py && git commit -m "refactor(phase2c): delegate cleanup to shared core/cleanup.py"
```

---

### Task 6: 编写单元测试

**Files:**
- Create: `tests/test_cleanup.py`

- [ ] **Step 1: 创建 `tests/test_cleanup.py`**

```python
"""测试座位预约超时清理逻辑"""

from datetime import date, datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from sqlalchemy import select

from core.cleanup import cleanup_expired_slots, _slot_cutoff
from core.lock import SeatLock
from models import Appointment, AppointmentStatus, Seat, SeatTimeSlot, TimeSlot, User


def make_user() -> User:
    return User(
        id="u1",
        username="testuser",
        password_hash="hash",
        display_name="Test",
        student_id="S001",
    )


def make_seat(id: str = "s1") -> Seat:
    return Seat(
        id=id,
        zone_id=1,
        seat_number="001",
        status="available",
    )


def make_sts(seat_id: str, date_val: date, slot: str, user_id: str, booked_at_override=None):
    """创建 SeatTimeSlot 测试数据"""
    booked_at = booked_at_override or datetime.now(timezone.utc)
    return SeatTimeSlot(
        id=f"sts-{seat_id}-{slot}",
        seat_id=seat_id,
        date=date_val,
        slot=TimeSlot(slot),
        user_id=user_id,
        booked_at=booked_at,
    )


def make_appt(id: str, user_id: str, seat_id: str, date_val: date, slot: str):
    """创建 Appointment 测试数据"""
    return Appointment(
        id=id,
        user_id=user_id,
        seat_id=seat_id,
        date=date_val,
        slot=TimeSlot(slot),
        status=AppointmentStatus.booked,
    )


class TestSlotCutoff:
    """_slot_cutoff 工具函数测试"""

    def test_morning_cutoff(self):
        d = date(2026, 7, 6)
        cutoff = _slot_cutoff(d, "morning")
        assert cutoff.hour == 8
        assert cutoff.minute == 30

    def test_afternoon_cutoff(self):
        d = date(2026, 7, 6)
        cutoff = _slot_cutoff(d, "afternoon")
        assert cutoff.hour == 13
        assert cutoff.minute == 30

    def test_evening_cutoff(self):
        d = date(2026, 7, 6)
        cutoff = _slot_cutoff(d, "evening")
        assert cutoff.hour == 18
        assert cutoff.minute == 30


class TestCleanupExpiredSlots:
    """cleanup_expired_slots 核心逻辑测试"""

    @pytest.mark.asyncio
    async def test_empty_table_returns_zero(self, db_session, redis_client):
        lock = SeatLock(redis_client)
        today = date.today()
        count = await cleanup_expired_slots(db_session, lock, today)
        assert count == 0

    @pytest.mark.asyncio
    async def test_expired_slot_is_cleaned(self, db_session, redis_client):
        """过期时段被清理，Appointment 标记为 expired"""
        lock = SeatLock(redis_client)
        today = date.today()

        user = make_user()
        seat = make_seat()
        db_session.add_all([user, seat])
        await db_session.flush()

        # 过去的时间（模拟已过期）
        old_time = datetime(2026, 7, 1, 0, 0, 0, tzinfo=timezone.utc)
        sts = make_sts(seat.id, today, "morning", user.id, booked_at_override=old_time)
        appt = make_appt("a1", user.id, seat.id, today, "morning")
        db_session.add_all([sts, appt])
        await db_session.commit()

        count = await cleanup_expired_slots(db_session, lock, today)
        assert count == 1

        # 验证 SeatTimeSlot 已删除
        sts_check = await db_session.execute(
            select(SeatTimeSlot).where(SeatTimeSlot.seat_id == seat.id)
        )
        assert sts_check.scalar_one_or_none() is None

        # 验证 Appointment 状态变为 expired
        await db_session.refresh(appt)
        assert appt.status == AppointmentStatus.expired

    @pytest.mark.asyncio
    async def test_future_slot_not_cleaned(self, db_session, redis_client):
        """未过期时段不被清理"""
        lock = SeatLock(redis_client)
        today = date.today()

        user = make_user()
        seat = make_seat()
        db_session.add_all([user, seat])
        await db_session.flush()

        sts = make_sts(seat.id, today, "morning", user.id)
        appt = make_appt("a1", user.id, seat.id, today, "morning")
        db_session.add_all([sts, appt])
        await db_session.commit()

        count = await cleanup_expired_slots(db_session, lock, today)
        assert count == 0

        sts_check = await db_session.execute(
            select(SeatTimeSlot).where(SeatTimeSlot.seat_id == seat.id)
        )
        assert sts_check.scalar_one_or_none() is not None

    @pytest.mark.asyncio
    async def test_tomorrow_slot_not_cleaned(self, db_session, redis_client):
        """明天的预约不被清理"""
        lock = SeatLock(redis_client)
        today = date.today()
        tomorrow = today.replace(day=today.day + 1) if today.day < 28 else today

        user = make_user()
        seat = make_seat()
        db_session.add_all([user, seat])
        await db_session.flush()

        old_time = datetime(2026, 7, 1, 0, 0, 0, tzinfo=timezone.utc)
        sts = make_sts(seat.id, tomorrow, "morning", user.id, booked_at_override=old_time)
        appt = make_appt("a1", user.id, seat.id, tomorrow, "morning")
        db_session.add_all([sts, appt])
        await db_session.commit()

        # 清理 today，不应影响 tomorrow
        count = await cleanup_expired_slots(db_session, lock, today)
        assert count == 0

        # tomorrow 的记录还在
        sts_check = await db_session.execute(
            select(SeatTimeSlot).where(SeatTimeSlot.seat_id == seat.id)
        )
        assert sts_check.scalar_one_or_none() is not None

    @pytest.mark.asyncio
    async def test_mixed_slots_expired_and_fresh(self, db_session, redis_client):
        """过期+未过期的混合场景，只删过期的"""
        lock = SeatLock(redis_client)
        today = date.today()

        user = make_user()
        seat = make_seat()
        db_session.add_all([user, seat])
        await db_session.flush()

        old_time = datetime(2026, 7, 1, 0, 0, 0, tzinfo=timezone.utc)

        # 过期
        sts1 = make_sts(seat.id, today, "morning", user.id, booked_at_override=old_time)
        appt1 = make_appt("a1", user.id, seat.id, today, "morning")
        # 未过期
        sts2 = make_sts(seat.id, today, "afternoon", user.id)
        appt2 = make_appt("a2", user.id, seat.id, today, "afternoon")
        db_session.add_all([sts1, appt1, sts2, appt2])
        await db_session.commit()

        count = await cleanup_expired_slots(db_session, lock, today)
        assert count == 1

        # morning 被删，afternoon 保留
        all_sts = (await db_session.execute(select(SeatTimeSlot))).scalars().all()
        assert len(all_sts) == 1
        assert all_sts[0].slot == TimeSlot.afternoon

    @pytest.mark.asyncio
    async def test_redis_lock_released_on_cleanup(self, db_session, redis_client):
        """过期清理时 Redis key 被释放"""
        lock = SeatLock(redis_client)
        today = date.today()
        date_str = str(today)

        user = make_user()
        seat = make_seat()
        db_session.add_all([user, seat])
        await db_session.flush()

        # 先设置 Redis 锁
        await lock.acquire(seat.id, date_str, "morning", user.id, ttl=300)
        assert await lock.is_locked(seat.id, date_str, "morning") is True

        old_time = datetime(2026, 7, 1, 0, 0, 0, tzinfo=timezone.utc)
        sts = make_sts(seat.id, today, "morning", user.id, booked_at_override=old_time)
        appt = make_appt("a1", user.id, seat.id, today, "morning")
        db_session.add_all([sts, appt])
        await db_session.commit()

        await cleanup_expired_slots(db_session, lock, today)

        # Redis key 应被释放
        assert await lock.is_locked(seat.id, date_str, "morning") is False

    @pytest.mark.asyncio
    async def test_specific_slot_cleans_only_that_slot(self, db_session, redis_client):
        """slot='morning' 时只清理 morning，不影响其他时段"""
        lock = SeatLock(redis_client)
        today = date.today()

        user = make_user()
        seat = make_seat()
        db_session.add_all([user, seat])
        await db_session.flush()

        old_time = datetime(2026, 7, 1, 0, 0, 0, tzinfo=timezone.utc)

        sts1 = make_sts(seat.id, today, "morning", user.id, booked_at_override=old_time)
        appt1 = make_appt("a1", user.id, seat.id, today, "morning")
        sts2 = make_sts(seat.id, today, "evening", user.id, booked_at_override=old_time)
        appt2 = make_appt("a2", user.id, seat.id, today, "evening")
        db_session.add_all([sts1, appt1, sts2, appt2])
        await db_session.commit()

        # 只清理 morning
        count = await cleanup_expired_slots(db_session, lock, today, slot="morning")
        assert count == 1

        all_sts = (await db_session.execute(select(SeatTimeSlot))).scalars().all()
        assert len(all_sts) == 1
        assert all_sts[0].slot == TimeSlot.evening
```

- [ ] **Step 2: 运行新测试验证通过**

```bash
cd deep_research_scaffold && uv run pytest tests/test_cleanup.py -v
```

预期：7 tests passed。

- [ ] **Step 3: 运行全部测试确保不破坏**

```bash
cd deep_research_scaffold && uv run pytest tests/ -v
```

预期：64 tests passed（原有 57 + 新增 7）。

- [ ] **Step 4: Commit**

```bash
cd deep_research_scaffold && git add tests/test_cleanup.py && git commit -m "test(phase2c): add cleanup logic unit tests"
```

---

### Task 7: Docker Compose 添加 Celery 服务

**Files:**
- Modify: `docker-compose.yml`

- [ ] **Step 1: 在 `docker-compose.yml` 中添加 celery_worker 和 celery_beat**

在 `redis` 服务块后追加：

```yaml
  celery_worker:
    build: .
    command: celery -A tasks.celery_app worker --loglevel=info
    environment:
      - APP_ENV=production
    depends_on:
      - postgres
      - redis
    restart: unless-stopped

  celery_beat:
    build: .
    command: celery -A tasks.celery_app beat --loglevel=info
    environment:
      - APP_ENV=production
    depends_on:
      - postgres
      - redis
    restart: unless-stopped
```

完整 `docker-compose.yml` 变为：

```yaml
version: "3.8"

services:
  app:
    build: .
    ports:
      - "8000:8000"
    environment:
      - APP_ENV=production
      - CONFIG_PATH=/app/config.example.json
    depends_on:
      - postgres
      - redis
    restart: unless-stopped

  postgres:
    image: postgres:15-alpine
    environment:
      POSTGRES_USER: library
      POSTGRES_PASSWORD: library123
      POSTGRES_DB: library
    ports:
      - "5432:5432"
    volumes:
      - pgdata:/var/lib/postgresql/data
    restart: unless-stopped

  redis:
    image: redis:7-alpine
    ports:
      - "6379:6379"
    restart: unless-stopped

  celery_worker:
    build: .
    command: celery -A tasks.celery_app worker --loglevel=info
    environment:
      - APP_ENV=production
    depends_on:
      - postgres
      - redis
    restart: unless-stopped

  celery_beat:
    build: .
    command: celery -A tasks.celery_app beat --loglevel=info
    environment:
      - APP_ENV=production
    depends_on:
      - postgres
      - redis
    restart: unless-stopped

volumes:
  pgdata:
```

- [ ] **Step 2: Commit**

```bash
cd deep_research_scaffold && git add docker-compose.yml && git commit -m "feat(phase2c): add celery worker and beat to docker-compose"
```

---

### Task 8: 更新 CLAUDE.md 记录 Phase 2c 完成状态

**Files:**
- Modify: `CLAUDE.md`

- [ ] **Step 1: 更新进度和结构**

在 CLAUDE.md 中：
1. 将 Phase 2c 从"下一步"移到"已完成"区域
2. 在项目结构中添加 `app/core/cleanup.py` 和 `app/tasks/` 包

- [ ] **Step 2: Commit**

```bash
cd deep_research_scaffold && git add CLAUDE.md && git commit -m "docs(phase2c): update CLAUDE.md with completion status"
```

---

### Task 9: 全量测试 + 最终验证

- [ ] **Step 1: 运行全量测试**

```bash
cd deep_research_scaffold && uv run pytest tests/ -v
```

预期：64 tests passed。

- [ ] **Step 2: 最终 commit（如有遗漏变更）**

```bash
cd deep_research_scaffold && git status
```

如有未提交文件，按需提交。
```

---

## 自检清单

1. **Spec 覆盖：**
   - `app/core/cleanup.py` → Task 2
   - `app/tasks/celery_app.py` → Task 3
   - `app/tasks/cleanup.py` → Task 4
   - SeatService 修改 → Task 5
   - Docker Compose 变更 → Task 7
   - pyproject.toml 依赖 → Task 1
   - 测试 → Task 6
   - 覆盖完整，无遗漏。

2. **占位符扫描：** 无 TBD/TODO，所有步骤包含完整代码。

3. **类型一致性：**
   - `cleanup_expired_slots(db, lock, date_value, slot=None)` — 所有调用点参数一致
   - `SeatLock(redis_client)` — Task 4、Task 6 中创建方式一致
   - `get_settings().redis_url` — Task 3、Task 4 中使用一致
   - `_slot_cutoff(date_value, slot)` — Task 2 定义，Task 6 测试引用一致
