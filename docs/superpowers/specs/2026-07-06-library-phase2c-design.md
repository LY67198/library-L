# Phase 2c: Celery 超时释放 — 设计文档

## 概述

Phase 2c 引入 Celery Beat 定时任务，主动扫描并释放过期的座位预约。与现有懒清理（`SeatService._cleanup_expired_slots`）形成"主力 + 兜底"的双重保障。

## 技术决策摘要

| 模块 | 决策 |
|------|------|
| 任务调度 | Celery Beat 每 5 分钟触发 |
| 消息代理 | Redis（复用现有 `REDIS_URL`） |
| 清理策略 | 扫当天所有时段，释放 `slot_start + 30min < now` 的记录 |
| 懒清理 | 保留，作为 Celery 挂了时的兜底 |
| 代码结构 | 清理逻辑抽离到 `app/core/cleanup.py`，Celery 和 SeatService 共用 |

## 架构

```
                    Celery Beat
                        │
                  每 5 分钟触发
                        │
                        ▼
              release_expired_slots()
              ┌──────────────────────┐
              │ 扫描今天所有           │
              │ SeatTimeSlot          │
              │ slot_start+30 < now   │
              │   ├─ 删除 SeatTimeSlot│
              │   ├─ Redis key 释放   │
              │   └─ Appointment→     │
              │      expired          │
              └──────────────────────┘
                        │
              ┌─────────┴─────────┐
              ▼                   ▼
        Celery Worker     现有懒清理（保留）
        （主力）           （兜底）
```

## 代码结构变更

```
app/
├── tasks/                          ← 新增包
│   ├── __init__.py
│   ├── celery_app.py               ← Celery 实例 + Beat 配置
│   └── cleanup.py                  ← release_expired_slots 任务
├── core/
│   └── cleanup.py                  ← 新增：抽离的纯清理逻辑
├── backend/
│   └── service/
│       └── seat_service.py         ← 修改：_cleanup 改为调用 core/cleanup
tests/
└── test_cleanup.py                 ← 新增：清理逻辑单元测试
```

## 核心接口

### `app/core/cleanup.py`

```python
from datetime import date, time, timezone, datetime
from sqlalchemy import and_, select
from sqlalchemy.ext.asyncio import AsyncSession
from core.lock import SeatLock
from models import Appointment, AppointmentStatus, SeatTimeSlot, TimeSlot

SLOT_TIMES = {
    "morning": (time(8, 0), time(12, 0)),
    "afternoon": (time(13, 0), time(17, 0)),
    "evening": (time(18, 0), time(22, 0)),
}

async def cleanup_expired_slots(
    db: AsyncSession,
    lock: SeatLock,
    date_value: date,
    slot: str | None = None,
) -> int:
    """清理过期未签到的预约。

    参数：
        date_value: 要清理的日期（通常为今天）
        slot: 可选，不传则清理所有时段

    返回：
        清理的 SeatTimeSlot 条数
    """
    slots_to_check = [slot] if slot else list(SLOT_TIMES.keys())
    cleaned = 0

    for s in slots_to_check:
        slot_start, _ = SLOT_TIMES[s]
        slot_start_dt = datetime.combine(date_value, slot_start, tzinfo=timezone.utc)
        cutoff = slot_start_dt.replace(minute=slot_start_dt.minute + 30)

        if datetime.now(timezone.utc) < cutoff:
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
        expired = result.scalars().all()
        for sts in expired:
            await lock.release(sts.seat_id, str(date_value), s)
            await db.delete(sts)

        if expired:
            # 批量更新 Appointment 状态
            appt_ids = []
            # 需要单独查出 appointment id
            for sts in expired:
                appt_result = await db.execute(
                    select(Appointment).where(
                        and_(
                            Appointment.seat_id == sts.seat_id,
                            Appointment.date == date_value,
                            Appointment.slot == TimeSlot(s),
                            Appointment.status == AppointmentStatus.booked,
                        )
                    )
                )
                appt = appt_result.scalar_one_or_none()
                if appt:
                    appt.status = AppointmentStatus.expired

        cleaned += len(expired)

    if cleaned:
        await db.commit()
    return cleaned
```

### `app/tasks/cleanup.py`

```python
from datetime import date, datetime, timezone
from core.database import async_session_factory
from core.lock import SeatLock
from core.cleanup import cleanup_expired_slots
from .celery_app import celery_app
import redis.asyncio as aioredis
from app.config import settings

@celery_app.task(name="release_expired_slots")
def release_expired_slots() -> int:
    """Celery 定时任务：清理当天所有过期的座位预约。"""
    async def _run():
        redis_client = aioredis.from_url(settings.REDIS_URL, protocol=2)
        lock = SeatLock(redis_client)
        async with async_session_factory() as db:
            today = date.today()
            count = await cleanup_expired_slots(db, lock, today)
        await redis_client.aclose()
        return count

    import asyncio
    return asyncio.run(_run())
```

### `app/tasks/celery_app.py`

```python
from celery import Celery
from celery.schedules import crontab
from app.config import settings

celery_app = Celery(
    "library",
    broker=settings.REDIS_URL,
    broker_connection_retry_on_startup=True,
)

celery_app.conf.timezone = "UTC"
celery_app.conf.beat_schedule = {
    "release-expired-slots": {
        "task": "release_expired_slots",
        "schedule": crontab(minute="*/5"),
    },
}
```

## SeatService 修改

`SeatService._cleanup_expired_slots` 改为调用公共函数：

```python
# app/backend/service/seat_service.py

from core.cleanup import cleanup_expired_slots

class SeatService:
    async def _cleanup_expired_slots(self, date_value: Date, slot: str) -> None:
        await cleanup_expired_slots(self._db, self._lock, date_value, slot)
```

保留懒清理——Celery 挂了时，用户正常操作仍会触发清理。

## Docker Compose 变更

新增两个服务：

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

## 依赖新增

```toml
# pyproject.toml
"celery[redis]>=5.4",
```

dev 依赖无新增（测试中直接 `await` 异步任务函数，不需要 worker）。

## 测试策略

| 层级 | 测什么 | 怎么测 |
|------|--------|--------|
| 单元 | `cleanup_expired_slots` 函数 | fakeredis + aiosqlite，验证过期/未过期区分 |
| 单元 | Celery 任务定义 | 直接 `await release_expired_slots()`，不依赖 worker |
| 集成 | 懒清理仍正常工作 | 现有 `test_seat_api.py` 过期清理用例继续通过 |

**测试用例：**

1. 空表 → 返回 0
2. 一个过期 slot + 一个未过期 → 只删过期的那条
3. 过期 slot 的 Appointment 状态 `booked` → `expired`
4. 过期 slot 的 Redis key 被释放
5. 明天的预约不被清理（跨天检查）
6. 多时段混合：morning 过期、afternoon 未过期、evening 过期

**明确不测：** Celery Beat 调度逻辑（框架行为）、worker 进程启动（环境问题）、Redis 断连重试（运维层面）。

## 不清算的内容

- 消息队列重试/死信队列（Celery 默认行为足够）
- 监控告警（Phase 3 可观测性统一做）
- 时区处理（统一 UTC）
