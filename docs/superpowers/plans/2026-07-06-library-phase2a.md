# Phase 2a: 用户系统 + 座位预约 — 实现计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 实现用户认证和座位预约的核心闭环：注册 → 登录 → 选座 → 预约 → 取消

**Architecture:** 在现有 FastAPI + LangGraph 脚手架上新增 `app/core/`（数据库/安全/锁）、`app/models/`（SQLAlchemy 模型）、`app/backend/router/auth_router` + `seat_router`、`app/backend/service/auth_service` + `seat_service`。Agent 层把 `reservation_stub_node` 升级为真实 `reservation_subgraph`。API 层全异步（async SQLAlchemy + asyncpg + async Redis），Agent 层通过 sync wrapper (asyncio.run) 桥接。

**Tech Stack:** FastAPI, LangGraph, SQLAlchemy 2.0 async, asyncpg, Alembic, Redis (redis-py async), python-jose, passlib[bcrypt], pytest + fakeredis + aiosqlite

---

### Task 1: 安装新依赖

**Files:**
- Modify: `pyproject.toml`

- [ ] **Step 1: 更新 pyproject.toml 添加 Phase 2a 依赖**

```toml
[project]
name = "deep-research-scaffold"
version = "0.1.0"
description = "A reusable FastAPI + LangGraph deep research scaffold"
requires-python = ">=3.10"
dependencies = [
  "fastapi>=0.115.0",
  "uvicorn[standard]>=0.30.0",
  "pydantic>=2.8.0",
  "pydantic-settings>=2.4.0",
  "langgraph>=0.2.0",
  "sqlalchemy[asyncio]>=2.0",
  "asyncpg>=0.30",
  "alembic>=1.14",
  "python-jose[cryptography]>=3.3",
  "passlib[bcrypt]>=1.7",
  "redis[hiredis]>=5.0",
]
```

- [ ] **Step 2: 同步安装依赖**

```bash
cd deep_research_scaffold && uv sync
```

- [ ] **Step 3: 安装 dev 依赖**

```bash
cd deep_research_scaffold && uv sync --group dev
```

手动编辑 `pyproject.toml` 追加 dev 依赖：

```toml
[dependency-groups]
dev = [
    "pytest>=9.1.1",
    "fakeredis[lua]>=2.22",
    "httpx>=0.28",
    "aiosqlite>=0.20",
]
```

然后 `uv sync --group dev`。

- [ ] **Step 4: 验证关键包可导入**

```bash
cd deep_research_scaffold && uv run python -c "
import sqlalchemy; print('sqlalchemy:', sqlalchemy.__version__)
import asyncpg; print('asyncpg:', asyncpg.__version__)
import redis.asyncio; print('redis:', redis.__version__)
import jose; print('jose ok')
import passlib; print('passlib ok')
import alembic; print('alembic:', alembic.__version__)
import fakeredis; print('fakeredis ok')
import aiosqlite; print('aiosqlite:', aiosqlite.__version__)
"
```

- [ ] **Step 5: Commit**

```bash
cd deep_research_scaffold && git add pyproject.toml uv.lock && git commit -m "$(cat <<'EOF'
chore: add Phase 2a dependencies — SQLAlchemy async, Alembic, JWT, Redis, passlib

Co-Authored-By: Claude Opus 4.6 <noreply@anthropic.com>
EOF
)"
```

---

### Task 2: 核心基础设施 — database + settings 扩展

**Files:**
- Create: `app/core/__init__.py`
- Create: `app/core/database.py`
- Modify: `app/backend/config/settings.py`

- [ ] **Step 1: 编写 database.py**

```python
"""异步数据库引擎与会话工厂"""

from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from backend.config.settings import get_settings

_engine = None
_session_factory = None


def _get_database_url() -> str:
    settings = get_settings()
    return settings.database_url


def get_engine():
    global _engine
    if _engine is None:
        _engine = create_async_engine(_get_database_url(), echo=False)
    return _engine


def get_session_factory() -> async_sessionmaker[AsyncSession]:
    global _session_factory
    if _session_factory is None:
        _session_factory = async_sessionmaker(get_engine(), expire_on_commit=False)
    return _session_factory


async def get_db() -> AsyncSession:
    """FastAPI 依赖 — 每个请求一个会话"""
    factory = get_session_factory()
    async with factory() as session:
        try:
            yield session
        finally:
            await session.close()
```

- [ ] **Step 2: 创建 core/__init__.py**

```python
"""核心基础设施 — 数据库、安全、分布式锁"""
```

- [ ] **Step 3: 扩展 settings.py，新增 database_url + JWT + Redis 配置**

读取现有 `app/backend/config/settings.py`，在 `AppSettings` 类中追加字段：

```python
database_url: str = "postgresql+asyncpg://library:library123@localhost:5432/library"
jwt_secret_key: str = "change-me-in-production"
jwt_algorithm: str = "HS256"
access_token_expire_minutes: int = 30
refresh_token_expire_days: int = 7
redis_url: str = "redis://localhost:6379/0"
```

同时在文件底部添加单例获取函数（与现有模块风格一致）：

```python
_SETTINGS: AppSettings | None = None


def get_settings() -> AppSettings:
    global _SETTINGS
    if _SETTINGS is None:
        _SETTINGS = AppSettings()
    return _SETTINGS
```

- [ ] **Step 4: Commit**

```bash
cd deep_research_scaffold && git add app/core/ app/backend/config/settings.py && git commit -m "$(cat <<'EOF'
feat: add database engine, session factory, and extended settings

Co-Authored-By: Claude Opus 4.6 <noreply@anthropic.com>
EOF
)"
```

---

### Task 3: SQLAlchemy 模型

**Files:**
- Create: `app/models/__init__.py`
- Create: `app/models/base.py`
- Create: `app/models/user.py`
- Create: `app/models/floor.py`
- Create: `app/models/zone.py`
- Create: `app/models/seat.py`
- Create: `app/models/seat_time_slot.py`
- Create: `app/models/appointment.py`

- [ ] **Step 1: 编写 base.py**

```python
"""SQLAlchemy 声明式基类"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

from sqlalchemy import DateTime, func
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column
from sqlalchemy.dialects.postgresql import UUID


class Base(DeclarativeBase):
    pass


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


def new_uuid() -> str:
    return str(uuid.uuid4())
```

- [ ] **Step 2: 编写 user.py**

```python
"""用户模型"""

from __future__ import annotations

from sqlalchemy import Boolean, String
from sqlalchemy.orm import Mapped, mapped_column

from .base import Base, new_uuid, utcnow


class User(Base):
    __tablename__ = "users"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_uuid)
    username: Mapped[str] = mapped_column(String(32), unique=True, nullable=False, index=True)
    password_hash: Mapped[str] = mapped_column(String(128), nullable=False)
    display_name: Mapped[str] = mapped_column(String(32), nullable=False)
    student_id: Mapped[str] = mapped_column(String(32), unique=True, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
```

（加上 `from datetime import datetime` at top）

- [ ] **Step 3: 编写 floor.py + zone.py**

```python
# floor.py
"""楼层模型"""

from __future__ import annotations

from sqlalchemy import Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import Base


class Floor(Base):
    __tablename__ = "floors"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(16), nullable=False)
    sort_order: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    zones: Mapped[list["Zone"]] = relationship("Zone", back_populates="floor", lazy="selectin")


# zone.py
"""区域模型"""

from __future__ import annotations

from sqlalchemy import Enum, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import Base

import enum


class ZoneType(str, enum.Enum):
    open = "open"
    room = "room"
    electronic = "electronic"


class Zone(Base):
    __tablename__ = "zones"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    floor_id: Mapped[int] = mapped_column(Integer, ForeignKey("floors.id"), nullable=False)
    name: Mapped[str] = mapped_column(String(32), nullable=False)
    zone_type: Mapped[ZoneType] = mapped_column(Enum(ZoneType, name="zone_type_enum"), default=ZoneType.open, nullable=False)
    sort_order: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    floor: Mapped["Floor"] = relationship("Floor", back_populates="zones")
    seats: Mapped[list["Seat"]] = relationship("Seat", back_populates="zone", lazy="selectin")
```

- [ ] **Step 4: 编写 seat.py + seat_time_slot.py**

```python
# seat.py
"""座位模型"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import Enum, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import Base, new_uuid

import enum


class SeatStatus(str, enum.Enum):
    available = "available"
    disabled = "disabled"


class Seat(Base):
    __tablename__ = "seats"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_uuid)
    zone_id: Mapped[int] = mapped_column(Integer, ForeignKey("zones.id"), nullable=False)
    seat_number: Mapped[str] = mapped_column(String(16), nullable=False)
    status: Mapped[SeatStatus] = mapped_column(Enum(SeatStatus, name="seat_status_enum"), default=SeatStatus.available, nullable=False)

    zone: Mapped["Zone"] = relationship("Zone", back_populates="seats")
    time_slots: Mapped[list["SeatTimeSlot"]] = relationship("SeatTimeSlot", back_populates="seat", lazy="selectin")
    appointments: Mapped[list["Appointment"]] = relationship("Appointment", back_populates="seat", lazy="selectin")


# seat_time_slot.py
"""座位时段占用模型 — 核心并发表"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import Date, Enum, ForeignKey, Integer, String, DateTime, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import Base, new_uuid, utcnow

import enum


class TimeSlot(str, enum.Enum):
    morning = "morning"
    afternoon = "afternoon"
    evening = "evening"


class SeatTimeSlot(Base):
    __tablename__ = "seat_time_slots"
    __table_args__ = (
        UniqueConstraint("seat_id", "date", "slot", name="uq_seat_date_slot"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_uuid)
    seat_id: Mapped[str] = mapped_column(String(36), ForeignKey("seats.id"), nullable=False, index=True)
    date: Mapped[datetime.date] = mapped_column(Date, nullable=False)
    slot: Mapped[TimeSlot] = mapped_column(Enum(TimeSlot, name="time_slot_enum"), nullable=False)
    user_id: Mapped[str] = mapped_column(String(36), ForeignKey("users.id"), nullable=False)
    booked_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    version: Mapped[int] = mapped_column(Integer, default=1, nullable=False)

    seat: Mapped["Seat"] = relationship("Seat", back_populates="time_slots")
    user: Mapped["User"] = relationship("User")
```

- [ ] **Step 5: 编写 appointment.py**

```python
"""预约记录模型 — 操作流水"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import Date, Enum, ForeignKey, Integer, String, DateTime
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import Base, new_uuid, utcnow
from .seat_time_slot import TimeSlot

import enum


class AppointmentStatus(str, enum.Enum):
    booked = "booked"
    checked_in = "checked_in"
    cancelled = "cancelled"
    expired = "expired"


class Appointment(Base):
    __tablename__ = "appointments"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_uuid)
    user_id: Mapped[str] = mapped_column(String(36), ForeignKey("users.id"), nullable=False, index=True)
    seat_id: Mapped[str] = mapped_column(String(36), ForeignKey("seats.id"), nullable=False)
    date: Mapped[datetime.date] = mapped_column(Date, nullable=False)
    slot: Mapped[TimeSlot] = mapped_column(Enum(TimeSlot, name="appointment_slot_enum"), nullable=False)
    status: Mapped[AppointmentStatus] = mapped_column(Enum(AppointmentStatus, name="appointment_status_enum"), default=AppointmentStatus.booked, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)

    user: Mapped["User"] = relationship("User")
    seat: Mapped["Seat"] = relationship("Seat", back_populates="appointments")
```

- [ ] **Step 6: 编写 models/__init__.py**

```python
"""数据模型层"""

from .base import Base, new_uuid, utcnow
from .user import User
from .floor import Floor
from .zone import Zone, ZoneType
from .seat import Seat, SeatStatus
from .seat_time_slot import SeatTimeSlot, TimeSlot
from .appointment import Appointment, AppointmentStatus

__all__ = [
    "Base",
    "new_uuid",
    "utcnow",
    "User",
    "Floor",
    "Zone",
    "ZoneType",
    "Seat",
    "SeatStatus",
    "SeatTimeSlot",
    "TimeSlot",
    "Appointment",
    "AppointmentStatus",
]
```

- [ ] **Step 7: 验证模型定义无语法错误**

```bash
cd deep_research_scaffold && uv run python -c "
import sys; sys.path.insert(0, 'app')
from models import Base, User, Floor, Zone, Seat, SeatTimeSlot, Appointment
print('All models imported OK')
print('Tables:', list(Base.metadata.tables.keys()))
"
```

预期输出包含 `users`, `floors`, `zones`, `seats`, `seat_time_slots`, `appointments`。

- [ ] **Step 8: Commit**

```bash
cd deep_research_scaffold && git add app/models/ && git commit -m "$(cat <<'EOF'
feat: add SQLAlchemy models — User, Floor, Zone, Seat, SeatTimeSlot, Appointment

Co-Authored-By: Claude Opus 4.6 <noreply@anthropic.com>
EOF
)"
```

---

### Task 4: Alembic 数据库迁移

**Files:**
- Create: `migrations/` (Alembic 自动生成)
- Create: `alembic.ini`
- Modify: `migrations/env.py`
- Modify: `app/models/base.py` (确保 Base.metadata 可被 alembic 引用)

- [ ] **Step 1: 初始化 Alembic**

```bash
cd deep_research_scaffold && uv run alembic init migrations
```

- [ ] **Step 2: 配置 alembic.ini — 设置数据库 URL**

```ini
# alembic.ini
[alembic]
script_location = migrations
sqlalchemy.url = postgresql+asyncpg://library:library123@localhost:5432/library
```

- [ ] **Step 3: 修改 migrations/env.py — 设置 target_metadata**

```python
"""Alembic 迁移环境配置"""

import asyncio
import sys
from pathlib import Path

APP_DIR = Path(__file__).resolve().parents[1] / "app"
if str(APP_DIR) not in sys.path:
    sys.path.insert(0, str(APP_DIR))

from models import Base
from core.database import get_engine
from backend.config.settings import get_settings

target_metadata = Base.metadata


def run_migrations_offline() -> None:
    """以 '离线' 模式运行迁移"""
    context.configure(
        url=get_settings().database_url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )
    with context.begin_transaction():
        context.run_migrations()


def do_run_migrations(connection):
    context.configure(connection=connection, target_metadata=target_metadata)
    with context.begin_transaction():
        context.run_migrations()


async def run_async_migrations():
    engine = get_engine()
    async with engine.connect() as connection:
        await connection.run_sync(do_run_migrations)
    await engine.dispose()


def run_migrations_online() -> None:
    """以 '在线' 模式运行迁移"""
    asyncio.run(run_async_migrations())


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
```

注意：需要保留现有 env.py 的结构，主要是修改 `target_metadata` 和 `run_migrations_online`。其余保留 Alembic 生成的内容。

- [ ] **Step 4: 生成初始迁移**

```bash
cd deep_research_scaffold && uv run alembic revision --autogenerate -m "initial: users floors zones seats seat_time_slots appointments"
```

- [ ] **Step 5: Commit**

```bash
cd deep_research_scaffold && git add alembic.ini migrations/ && git commit -m "$(cat <<'EOF'
chore: add Alembic migration setup with initial schema

Co-Authored-By: Claude Opus 4.6 <noreply@anthropic.com>
EOF
)"
```

---

### Task 5: 安全模块 — JWT + 密码哈希

**Files:**
- Create: `app/core/security.py`

- [ ] **Step 1: 编写 security.py**

```python
"""安全模块 — JWT 签发/验证 + 密码哈希"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from jose import JWTError, jwt
from passlib.context import CryptContext

from backend.config.settings import get_settings

_pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def hash_password(password: str) -> str:
    return _pwd_context.hash(password)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    return _pwd_context.verify(plain_password, hashed_password)


def create_access_token(user_id: str) -> str:
    settings = get_settings()
    expire = datetime.now(timezone.utc) + timedelta(minutes=settings.access_token_expire_minutes)
    payload = {
        "sub": user_id,
        "exp": expire,
        "type": "access",
    }
    return jwt.encode(payload, settings.jwt_secret_key, algorithm=settings.jwt_algorithm)


def create_refresh_token(user_id: str) -> str:
    settings = get_settings()
    expire = datetime.now(timezone.utc) + timedelta(days=settings.refresh_token_expire_days)
    payload = {
        "sub": user_id,
        "exp": expire,
        "type": "refresh",
    }
    return jwt.encode(payload, settings.jwt_secret_key, algorithm=settings.jwt_algorithm)


def decode_token(token: str) -> dict:
    settings = get_settings()
    try:
        payload = jwt.decode(token, settings.jwt_secret_key, algorithms=[settings.jwt_algorithm])
        return payload
    except JWTError:
        raise ValueError("invalid_token")
```

- [ ] **Step 2: 编写单元测试 tests/test_security.py**

```python
"""安全模块单元测试"""

import pytest
from core.security import (
    create_access_token,
    create_refresh_token,
    decode_token,
    hash_password,
    verify_password,
)


def test_hash_and_verify_password():
    plain = "mypassword123"
    hashed = hash_password(plain)
    assert hashed != plain
    assert verify_password(plain, hashed)
    assert not verify_password("wrongpassword", hashed)


def test_create_and_decode_access_token():
    token = create_access_token("user-1")
    payload = decode_token(token)
    assert payload["sub"] == "user-1"
    assert payload["type"] == "access"
    assert "exp" in payload


def test_create_and_decode_refresh_token():
    token = create_refresh_token("user-1")
    payload = decode_token(token)
    assert payload["sub"] == "user-1"
    assert payload["type"] == "refresh"


def test_decode_invalid_token():
    with pytest.raises(ValueError, match="invalid_token"):
        decode_token("not.a.valid.token")


def test_refresh_token_rejected_as_access():
    refresh = create_refresh_token("user-1")
    payload = decode_token(refresh)
    assert payload["type"] == "refresh"
    # Not an access token — caller should check type
    assert payload["type"] != "access"
```

- [ ] **Step 3: 运行测试**

```bash
cd deep_research_scaffold && uv run pytest tests/test_security.py -v
```
预期：5 passed

- [ ] **Step 4: Commit**

```bash
cd deep_research_scaffold && git add app/core/security.py tests/test_security.py && git commit -m "$(cat <<'EOF'
feat: add JWT create/decode + bcrypt password hashing with tests

Co-Authored-By: Claude Opus 4.6 <noreply@anthropic.com>
EOF
)"
```

---

### Task 6: FastAPI 依赖注入 — get_db, get_current_user

**Files:**
- Create: `app/core/deps.py`

- [ ] **Step 1: 编写 deps.py**

```python
"""FastAPI 依赖 — 数据库会话 + 认证用户"""

from __future__ import annotations

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from .database import get_db
from .security import decode_token
from models import User

_bearer_scheme = HTTPBearer(auto_error=False)


async def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(_bearer_scheme),
    db: AsyncSession = Depends(get_db),
) -> User:
    """从 Bearer token 中提取当前用户。无 token 时返回 None 表示匿名。"""
    if credentials is None:
        return None
    try:
        payload = decode_token(credentials.credentials)
        if payload.get("type") != "access":
            return None
        user_id = payload.get("sub")
        if not user_id:
            return None
    except ValueError:
        return None

    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if user is None or not user.is_active:
        return None
    return user


async def get_required_user(
    user: User | None = Depends(get_current_user),
) -> User:
    """强制认证依赖 — 未登录返回 401"""
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"error": "invalid_token", "message": "请先登录"},
        )
    return user
```

- [ ] **Step 2: Commit**

```bash
cd deep_research_scaffold && git add app/core/deps.py && git commit -m "$(cat <<'EOF'
feat: add FastAPI auth dependencies — get_current_user, get_required_user

Co-Authored-By: Claude Opus 4.6 <noreply@anthropic.com>
EOF
)"
```

---

### Task 7: Redis 分布式锁

**Files:**
- Create: `app/core/lock.py`

- [ ] **Step 1: 编写 lock.py**

```python
"""Redis 分布式锁 — 座位预约并发控制"""

from __future__ import annotations

import redis.asyncio as aioredis


class SeatLock:
    """座位预约分布式锁。仅用于预约操作窗口的快速抢占，持久状态靠 PG。"""

    def __init__(self, redis_client: aioredis.Redis):
        self._redis = redis_client

    async def acquire(self, seat_id: str, date: str, slot: str,
                      user_id: str, ttl: int = 30) -> bool:
        """返回 True 表示抢锁成功"""
        key = f"seat:{seat_id}:{date}:{slot}"
        return await self._redis.set(key, user_id, nx=True, ex=ttl)

    async def release(self, seat_id: str, date: str, slot: str) -> None:
        """释放锁"""
        key = f"seat:{seat_id}:{date}:{slot}"
        await self._redis.delete(key)

    async def is_locked(self, seat_id: str, date: str, slot: str) -> bool:
        """检查是否被锁定"""
        key = f"seat:{seat_id}:{date}:{slot}"
        return await self._redis.exists(key) > 0
```

- [ ] **Step 2: 编写单元测试 tests/test_lock.py**

```python
"""Redis 分布式锁单元测试 — 使用 fakeredis"""

import pytest
from core.lock import SeatLock


@pytest.fixture
async def redis_client():
    import fakeredis.aioredis
    client = fakeredis.aioredis.FakeRedis()
    yield client
    await client.aclose()


@pytest.fixture
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
```

- [ ] **Step 3: 运行测试**

```bash
cd deep_research_scaffold && uv run pytest tests/test_lock.py -v
```
预期：5 passed

- [ ] **Step 4: Commit**

```bash
cd deep_research_scaffold && git add app/core/lock.py tests/test_lock.py && git commit -m "$(cat <<'EOF'
feat: add Redis distributed lock for seat booking with tests

Co-Authored-By: Claude Opus 4.6 <noreply@anthropic.com>
EOF
)"
```

---

### Task 8: Auth Schemas

**Files:**
- Create: `app/backend/schemas/auth.py`

- [ ] **Step 1: 编写 auth.py**

```python
"""认证相关 Pydantic 模型"""

from __future__ import annotations

from pydantic import BaseModel, Field


class RegisterRequest(BaseModel):
    username: str = Field(min_length=4, max_length=32)
    password: str = Field(min_length=8, max_length=128)
    display_name: str = Field(min_length=1, max_length=32)
    student_id: str = Field(min_length=1, max_length=32)


class RegisterResponse(BaseModel):
    user_id: str
    username: str


class LoginRequest(BaseModel):
    username: str
    password: str


class LoginResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"


class RefreshRequest(BaseModel):
    refresh_token: str


class RefreshResponse(BaseModel):
    access_token: str


class UserProfile(BaseModel):
    user_id: str
    username: str
    display_name: str
    student_id: str
```

- [ ] **Step 2: Commit**

```bash
cd deep_research_scaffold && git add app/backend/schemas/auth.py && git commit -m "$(cat <<'EOF'
feat: add auth request/response schemas

Co-Authored-By: Claude Opus 4.6 <noreply@anthropic.com>
EOF
)"
```

---

### Task 9: Auth Service

**Files:**
- Create: `app/backend/service/auth_service.py`

- [ ] **Step 1: 编写 auth_service.py**

```python
"""认证业务逻辑"""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from core.security import (
    create_access_token,
    create_refresh_token,
    decode_token,
    hash_password,
    verify_password,
)
from models import User


class AuthService:

    def __init__(self, db: AsyncSession):
        self._db = db

    async def register(
        self, username: str, password: str, display_name: str, student_id: str
    ) -> User:
        """注册新用户。username 或 student_id 重复时抛出 ValueError。"""
        # 检查 username 唯一
        result = await self._db.execute(select(User).where(User.username == username))
        if result.scalar_one_or_none():
            raise ValueError("用户名已存在")

        # 检查 student_id 唯一
        result = await self._db.execute(select(User).where(User.student_id == student_id))
        if result.scalar_one_or_none():
            raise ValueError("学号已存在")

        user = User(
            username=username,
            password_hash=hash_password(password),
            display_name=display_name,
            student_id=student_id,
        )
        self._db.add(user)
        await self._db.commit()
        await self._db.refresh(user)
        return user

    async def login(self, username: str, password: str) -> dict:
        """登录 — 返回 access_token + refresh_token"""
        result = await self._db.execute(select(User).where(User.username == username))
        user = result.scalar_one_or_none()
        if user is None or not verify_password(password, user.password_hash):
            raise ValueError("用户名或密码错误")
        if not user.is_active:
            raise ValueError("账号已被禁用")

        return {
            "access_token": create_access_token(user.id),
            "refresh_token": create_refresh_token(user.id),
            "token_type": "bearer",
        }

    async def refresh(self, refresh_token: str) -> str:
        """用 refresh_token 换取新的 access_token"""
        try:
            payload = decode_token(refresh_token)
            if payload.get("type") != "refresh":
                raise ValueError("invalid_token")
            user_id = payload.get("sub")
            if not user_id:
                raise ValueError("invalid_token")
        except ValueError:
            raise ValueError("invalid_token")

        result = await self._db.execute(select(User).where(User.id == user_id))
        user = result.scalar_one_or_none()
        if user is None or not user.is_active:
            raise ValueError("invalid_token")

        return create_access_token(user.id)

    async def get_user(self, user_id: str) -> User | None:
        result = await self._db.execute(select(User).where(User.id == user_id))
        return result.scalar_one_or_none()
```

- [ ] **Step 2: Commit**

```bash
cd deep_research_scaffold && git add app/backend/service/auth_service.py && git commit -m "$(cat <<'EOF'
feat: add AuthService — register, login, refresh token

Co-Authored-By: Claude Opus 4.6 <noreply@anthropic.com>
EOF
)"
```

---

### Task 10: Auth Router + 注册到 main

**Files:**
- Create: `app/backend/router/auth_router.py`
- Modify: `app/app_main.py`

- [ ] **Step 1: 编写 auth_router.py**

```python
"""认证接口 — 注册/登录/刷新Token/当前用户"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from core.database import get_db
from core.deps import get_current_user, get_required_user
from models import User
from backend.schemas.auth import (
    RegisterRequest,
    RegisterResponse,
    LoginRequest,
    LoginResponse,
    RefreshRequest,
    RefreshResponse,
    UserProfile,
)
from backend.service.auth_service import AuthService

router = APIRouter(prefix="/api/v1/auth", tags=["auth"])


@router.post("/register", response_model=RegisterResponse, status_code=status.HTTP_201_CREATED)
async def register(payload: RegisterRequest, db: AsyncSession = Depends(get_db)):
    service = AuthService(db)
    try:
        user = await service.register(
            username=payload.username,
            password=payload.password,
            display_name=payload.display_name,
            student_id=payload.student_id,
        )
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(e))
    return RegisterResponse(user_id=user.id, username=user.username)


@router.post("/login", response_model=LoginResponse)
async def login(payload: LoginRequest, db: AsyncSession = Depends(get_db)):
    service = AuthService(db)
    try:
        result = await service.login(payload.username, payload.password)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=str(e))
    return LoginResponse(**result)


@router.post("/refresh", response_model=RefreshResponse)
async def refresh(payload: RefreshRequest, db: AsyncSession = Depends(get_db)):
    service = AuthService(db)
    try:
        access_token = await service.refresh(payload.refresh_token)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"error": "invalid_token", "message": "Token 无效或已过期"},
        )
    return RefreshResponse(access_token=access_token)


@router.get("/me", response_model=UserProfile)
async def me(user: User = Depends(get_required_user)):
    return UserProfile(
        user_id=user.id,
        username=user.username,
        display_name=user.display_name,
        student_id=user.student_id,
    )
```

- [ ] **Step 2: 在 app_main.py 中注册 auth_router**

在 `from backend.router.book_router import router as book_router` 后添加一行：

```python
from backend.router.auth_router import router as auth_router
```

在 `app.include_router(book_router)` 后添加：

```python
    app.include_router(auth_router)
```

- [ ] **Step 3: Commit**

```bash
cd deep_research_scaffold && git add app/backend/router/auth_router.py app/app_main.py && git commit -m "$(cat <<'EOF'
feat: add auth REST API — register, login, refresh, me

Co-Authored-By: Claude Opus 4.6 <noreply@anthropic.com>
EOF
)"
```

---

### Task 11: Auth API 集成测试

**Files:**
- Create: `tests/test_auth_api.py`
- Modify: `tests/conftest.py`

- [ ] **Step 1: 扩展 conftest.py — 添加 async SQLite + fakeredis fixtures**

```python
"""测试配置 — 将 app/ 加入 Python 路径，提供 async fixtures"""

import sys
import asyncio
from pathlib import Path

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

APP_DIR = Path(__file__).resolve().parent.parent / "app"
if str(APP_DIR) not in sys.path:
    sys.path.insert(0, str(APP_DIR))


# --- Async SQLite for integration tests ---

TEST_DATABASE_URL = "sqlite+aiosqlite:///:memory:"


@pytest_asyncio.fixture(scope="function")
async def db_session():
    """每个测试独立的 SQLite 内存数据库"""
    from models import Base
    engine = create_async_engine(TEST_DATABASE_URL, echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    async with factory() as session:
        yield session
    await engine.dispose()


# --- fakeredis for Redis tests ---

@pytest_asyncio.fixture
async def redis_client():
    import fakeredis.aioredis
    client = fakeredis.aioredis.FakeRedis()
    yield client
    await client.aclose()
```

- [ ] **Step 2: 编写 test_auth_api.py**

```python
"""Auth API 集成测试 — 注册 → 登录 → refresh → me"""

import pytest
from httpx import ASGITransport, AsyncClient
from app_main import app


@pytest.mark.asyncio
async def test_register_success(db_session):
    # 重写 get_db 依赖，注入测试数据库
    from core.database import get_db as _get_db

    async def override_get_db():
        yield db_session

    app.dependency_overrides[_get_db] = override_get_db

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.post("/api/v1/auth/register", json={
            "username": "testuser1",
            "password": "password123",
            "display_name": "测试用户",
            "student_id": "2024001",
        })
        assert resp.status_code == 201
        data = resp.json()
        assert data["username"] == "testuser1"
        assert "user_id" in data

    app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_register_duplicate_username(db_session):
    async def override_get_db():
        yield db_session

    app.dependency_overrides[_get_db] = override_get_db

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # First registration
        await client.post("/api/v1/auth/register", json={
            "username": "dupuser",
            "password": "password123",
            "display_name": "重复用户",
            "student_id": "2024101",
        })
        # Second with same username
        resp = await client.post("/api/v1/auth/register", json={
            "username": "dupuser",
            "password": "password456",
            "display_name": "重复用户2",
            "student_id": "2024102",
        })
        assert resp.status_code == 409

    app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_login_success(db_session):
    async def override_get_db():
        yield db_session

    app.dependency_overrides[_get_db] = override_get_db

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # Register first
        await client.post("/api/v1/auth/register", json={
            "username": "loginuser",
            "password": "mypassword",
            "display_name": "登录用户",
            "student_id": "2024201",
        })
        # Then login
        resp = await client.post("/api/v1/auth/login", json={
            "username": "loginuser",
            "password": "mypassword",
        })
        assert resp.status_code == 200
        data = resp.json()
        assert "access_token" in data
        assert "refresh_token" in data
        assert data["token_type"] == "bearer"

    app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_login_wrong_password(db_session):
    async def override_get_db():
        yield db_session

    app.dependency_overrides[_get_db] = override_get_db

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        await client.post("/api/v1/auth/register", json={
            "username": "wrongpw",
            "password": "correct",
            "display_name": "错误密码测试",
            "student_id": "2024301",
        })
        resp = await client.post("/api/v1/auth/login", json={
            "username": "wrongpw",
            "password": "incorrect",
        })
        assert resp.status_code == 401

    app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_refresh_token_flow(db_session):
    async def override_get_db():
        yield db_session

    app.dependency_overrides[_get_db] = override_get_db

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        await client.post("/api/v1/auth/register", json={
            "username": "refreshuser",
            "password": "testpass123",
            "display_name": "刷新测试",
            "student_id": "2024401",
        })
        login_resp = await client.post("/api/v1/auth/login", json={
            "username": "refreshuser", "password": "testpass123",
        })
        refresh_token = login_resp.json()["refresh_token"]

        resp = await client.post("/api/v1/auth/refresh", json={"refresh_token": refresh_token})
        assert resp.status_code == 200
        data = resp.json()
        assert "access_token" in data

    app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_me_endpoint(db_session):
    async def override_get_db():
        yield db_session

    app.dependency_overrides[_get_db] = override_get_db

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        await client.post("/api/v1/auth/register", json={
            "username": "meuser",
            "password": "testpass123",
            "display_name": "Me测试",
            "student_id": "2024501",
        })
        login_resp = await client.post("/api/v1/auth/login", json={
            "username": "meuser", "password": "testpass123",
        })
        access_token = login_resp.json()["access_token"]

        resp = await client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {access_token}"})
        assert resp.status_code == 200
        data = resp.json()
        assert data["username"] == "meuser"
        assert data["display_name"] == "Me测试"

        # Without token should get 401
        resp2 = await client.get("/api/v1/auth/me")
        assert resp2.status_code == 401

    app.dependency_overrides.clear()
```

- [ ] **Step 3: 运行测试**

```bash
cd deep_research_scaffold && uv run pytest tests/test_auth_api.py -v
```
预期：6 passed

- [ ] **Step 4: Commit**

```bash
cd deep_research_scaffold && git add tests/conftest.py tests/test_auth_api.py && git commit -m "$(cat <<'EOF'
test: add auth API integration tests — register, login, refresh, me

Co-Authored-By: Claude Opus 4.6 <noreply@anthropic.com>
EOF
)"
```

---

### Task 12: Seat Schemas

**Files:**
- Create: `app/backend/schemas/seat.py`

- [ ] **Step 1: 编写 seat.py**

```python
"""座位相关 Pydantic 模型"""

from __future__ import annotations

from pydantic import BaseModel, Field


class BookRequest(BaseModel):
    date: str = Field(description="日期 YYYY-MM-DD")
    slot: str = Field(pattern="^(morning|afternoon|evening)$")


class BookResponse(BaseModel):
    appointment_id: str
    seat_id: str
    floor_name: str
    zone_name: str
    seat_number: str
    date: str
    slot: str


class SeatItem(BaseModel):
    seat_id: str
    floor_name: str
    zone_name: str
    seat_number: str
    status: str  # available / booked
    booked_by_me: bool


class SeatListResponse(BaseModel):
    seats: list[SeatItem]


class AppointmentItem(BaseModel):
    appointment_id: str
    seat_id: str
    floor_name: str
    zone_name: str
    seat_number: str
    date: str
    slot: str
    status: str


class AppointmentListResponse(BaseModel):
    appointments: list[AppointmentItem]


class CancelResponse(BaseModel):
    appointment_id: str
    status: str  # cancelled
```

- [ ] **Step 2: Commit**

```bash
cd deep_research_scaffold && git add app/backend/schemas/seat.py && git commit -m "$(cat <<'EOF'
feat: add seat booking request/response schemas

Co-Authored-By: Claude Opus 4.6 <noreply@anthropic.com>
EOF
)"
```

---

### Task 13: Seat Service

**Files:**
- Create: `app/backend/service/seat_service.py`

- [ ] **Step 1: 编写 seat_service.py**

```python
"""座位预约业务逻辑"""

from __future__ import annotations

from datetime import date as Date, datetime, time, timezone

from sqlalchemy import and_, select
from sqlalchemy.ext.asyncio import AsyncSession

from core.lock import SeatLock
from models import (
    Appointment,
    AppointmentStatus,
    Floor,
    Seat,
    SeatStatus,
    SeatTimeSlot,
    TimeSlot,
    User,
    Zone,
)

# 时段定义
SLOT_TIMES = {
    "morning": (time(8, 0), time(12, 0)),
    "afternoon": (time(13, 0), time(17, 0)),
    "evening": (time(18, 0), time(22, 0)),
}

GRACE_MINUTES = 30  # 时段开始后30分钟未签到视为过期


class SeatService:

    def __init__(self, db: AsyncSession, lock: SeatLock):
        self._db = db
        self._lock = lock

    async def _cleanup_expired_slots(self, date_value: Date, slot: str) -> None:
        """懒清理：释放过期未签到的预约"""
        slot_start = SLOT_TIMES[slot][0]
        cutoff = datetime.combine(date_value, slot_start, tzinfo=timezone.utc)
        # 时段开始 + 宽限时间的预约视为过期
        # 实际判断：booked_at < slot_start，且状态为 booked
        # 简化处理：只要是今天当前时段之前的未签到预约，都清理
        now = datetime.now(timezone.utc)
        slot_end = datetime.combine(date_value, SLOT_TIMES[slot][1], tzinfo=timezone.utc)

        result = await self._db.execute(
            select(SeatTimeSlot).join(Appointment).where(
                and_(
                    SeatTimeSlot.date == date_value,
                    SeatTimeSlot.slot == slot,
                    Appointment.status == AppointmentStatus.booked,
                    SeatTimeSlot.booked_at < slot_end,
                )
            )
        )
        expired = result.scalars().all()
        for sts in expired:
            await self._lock.release(sts.seat_id, str(date_value), slot)
            await self._db.delete(sts)
        if expired:
            await self._db.commit()

    async def list_seats(
        self,
        floor_id: int | None = None,
        zone_id: int | None = None,
        date_value: Date | None = None,
        slot: str | None = None,
        user_id: str | None = None,
    ) -> list[dict]:
        """查询座位列表，支持筛选。懒清理过期预约。"""
        if date_value and slot:
            await self._cleanup_expired_slots(date_value, slot)

        query = (
            select(Seat, Zone.name, Floor.name)
            .join(Zone, Seat.zone_id == Zone.id)
            .join(Floor, Zone.floor_id == Floor.id)
        )

        if floor_id:
            query = query.where(Floor.id == floor_id)
        if zone_id:
            query = query.where(Zone.id == zone_id)

        result = await self._db.execute(query)
        rows = result.all()

        seats = []
        for seat, zone_name, floor_name in rows:
            status = "available"
            booked_by_me = False

            if date_value and slot:
                sts_result = await self._db.execute(
                    select(SeatTimeSlot).where(
                        and_(
                            SeatTimeSlot.seat_id == seat.id,
                            SeatTimeSlot.date == date_value,
                            SeatTimeSlot.slot == slot,
                        )
                    )
                )
                existing = sts_result.scalar_one_or_none()
                if existing:
                    status = "booked"
                    if user_id and existing.user_id == user_id:
                        booked_by_me = True

            if seat.status == SeatStatus.disabled:
                status = "disabled"

            seats.append({
                "seat_id": seat.id,
                "floor_name": floor_name,
                "zone_name": zone_name,
                "seat_number": seat.seat_number,
                "status": status,
                "booked_by_me": booked_by_me,
            })

        return seats

    async def book_seat(
        self, seat_id: str, user_id: str, date_value: Date, slot: str
    ) -> dict:
        """预约座位 — Redis 抢锁 + PG 写入 + 双重保障"""
        date_str = str(date_value)

        # 验证 slot 合法
        if slot not in SLOT_TIMES:
            raise ValueError("无效的时段")

        # 验证日期不是过去
        today = datetime.now(timezone.utc).date()
        if date_value < today:
            raise ValueError("不能预约过去的日期")

        # 验证座位存在且可用
        result = await self._db.execute(select(Seat).where(Seat.id == seat_id))
        seat = result.scalar_one_or_none()
        if seat is None:
            raise ValueError("座位不存在")
        if seat.status == SeatStatus.disabled:
            raise ValueError("该座位暂不可用")

        # 检查用户是否同一时段已有预约
        existing = await self._db.execute(
            select(SeatTimeSlot).where(
                and_(
                    SeatTimeSlot.user_id == user_id,
                    SeatTimeSlot.date == date_value,
                    SeatTimeSlot.slot == slot,
                )
            )
        )
        if existing.scalar_one_or_none():
            raise ValueError("同一时段已有预约")

        # 第一层: Redis 快速抢占
        acquired = await self._lock.acquire(seat_id, date_str, slot, user_id, ttl=30)
        if not acquired:
            raise ValueError("座位已被预约")

        try:
            # 第二层: PG UNIQUE 约束
            slot_enum = TimeSlot(slot)
            sts = SeatTimeSlot(
                seat_id=seat_id,
                date=date_value,
                slot=slot_enum,
                user_id=user_id,
            )
            self._db.add(sts)

            appt = Appointment(
                user_id=user_id,
                seat_id=seat_id,
                date=date_value,
                slot=slot_enum,
                status=AppointmentStatus.booked,
            )
            self._db.add(appt)
            await self._db.commit()
            await self._db.refresh(appt)

            # 获取关联信息
            zone_result = await self._db.execute(
                select(Zone.name, Floor.name)
                .join(Floor, Zone.floor_id == Floor.id)
                .where(Zone.id == seat.zone_id)
            )
            zone_name, floor_name = zone_result.one()

            return {
                "appointment_id": appt.id,
                "seat_id": seat_id,
                "floor_name": floor_name,
                "zone_name": zone_name,
                "seat_number": seat.seat_number,
                "date": date_str,
                "slot": slot,
            }
        except Exception:
            await self._lock.release(seat_id, date_str, slot)
            raise

    async def list_appointments(self, user_id: str) -> list[dict]:
        """查询用户的所有预约"""
        result = await self._db.execute(
            select(Appointment, Seat.seat_number, Zone.name, Floor.name)
            .join(Seat, Appointment.seat_id == Seat.id)
            .join(Zone, Seat.zone_id == Zone.id)
            .join(Floor, Zone.floor_id == Floor.id)
            .where(Appointment.user_id == user_id)
            .order_by(Appointment.created_at.desc())
        )
        rows = result.all()

        return [
            {
                "appointment_id": appt.id,
                "seat_id": appt.seat_id,
                "floor_name": floor_name,
                "zone_name": zone_name,
                "seat_number": seat_number,
                "date": str(appt.date),
                "slot": appt.slot.value,
                "status": appt.status.value,
            }
            for appt, seat_number, zone_name, floor_name in rows
        ]

    async def cancel_appointment(self, appointment_id: str, user_id: str) -> dict:
        """取消预约"""
        result = await self._db.execute(
            select(Appointment).where(
                and_(
                    Appointment.id == appointment_id,
                    Appointment.user_id == user_id,
                )
            )
        )
        appt = result.scalar_one_or_none()
        if appt is None:
            raise ValueError("预约记录不存在")

        if appt.status == AppointmentStatus.cancelled:
            raise ValueError("预约已取消")

        if appt.status == AppointmentStatus.expired:
            raise ValueError("预约已过期")

        # 释放 Redis 锁 + 删除 seat_time_slot
        date_str = str(appt.date)
        slot_str = appt.slot.value
        await self._lock.release(appt.seat_id, date_str, slot_str)

        sts_result = await self._db.execute(
            select(SeatTimeSlot).where(
                and_(
                    SeatTimeSlot.seat_id == appt.seat_id,
                    SeatTimeSlot.date == appt.date,
                    SeatTimeSlot.slot == appt.slot,
                )
            )
        )
        sts = sts_result.scalar_one_or_none()
        if sts:
            await self._db.delete(sts)

        appt.status = AppointmentStatus.cancelled
        await self._db.commit()

        return {
            "appointment_id": appointment_id,
            "status": "cancelled",
        }
```

- [ ] **Step 2: Commit**

```bash
cd deep_research_scaffold && git add app/backend/service/seat_service.py && git commit -m "$(cat <<'EOF'
feat: add SeatService — list seats, book, cancel, lazy cleanup

Co-Authored-By: Claude Opus 4.6 <noreply@anthropic.com>
EOF
)"
```

---

### Task 14: Seat Router + 注册到 main

**Files:**
- Create: `app/backend/router/seat_router.py`
- Modify: `app/app_main.py`

- [ ] **Step 1: 编写 seat_router.py**

```python
"""座位预约接口 — 搜索/预约/取消/查询"""

from __future__ import annotations

from datetime import date as Date

import redis.asyncio as aioredis
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from core.database import get_db
from core.deps import get_required_user
from core.lock import SeatLock
from backend.config.settings import get_settings
from models import User
from backend.schemas.seat import (
    AppointmentItem,
    AppointmentListResponse,
    BookRequest,
    BookResponse,
    CancelResponse,
    SeatItem,
    SeatListResponse,
)
from backend.service.seat_service import SeatService

router = APIRouter(prefix="/api/v1", tags=["seats"])

_REDIS_CLIENT: aioredis.Redis | None = None
_SEAT_LOCK: SeatLock | None = None


def _get_redis() -> aioredis.Redis:
    global _REDIS_CLIENT
    if _REDIS_CLIENT is None:
        settings = get_settings()
        _REDIS_CLIENT = aioredis.from_url(settings.redis_url, decode_responses=False)
    return _REDIS_CLIENT


async def get_seat_lock() -> SeatLock:
    """FastAPI 依赖 — 提供 SeatLock 实例（测试时可 override）"""
    global _SEAT_LOCK
    if _SEAT_LOCK is None:
        _SEAT_LOCK = SeatLock(_get_redis())
    return _SEAT_LOCK


@router.get("/seats", response_model=SeatListResponse)
async def list_seats(
    floor_id: int | None = Query(None),
    zone_id: int | None = Query(None),
    date: str | None = Query(None, description="YYYY-MM-DD"),
    slot: str | None = Query(None, pattern="^(morning|afternoon|evening)$"),
    db: AsyncSession = Depends(get_db),
    lock: SeatLock = Depends(get_seat_lock),
    user: User | None = Depends(get_required_user),
):
    date_value = Date.fromisoformat(date) if date else None
    service = SeatService(db, lock)
    seats = await service.list_seats(
        floor_id=floor_id,
        zone_id=zone_id,
        date_value=date_value,
        slot=slot,
        user_id=user.id if user else None,
    )
    return SeatListResponse(seats=[SeatItem(**s) for s in seats])


@router.post("/seats/{seat_id}/book", response_model=BookResponse)
async def book_seat(
    seat_id: str,
    payload: BookRequest,
    db: AsyncSession = Depends(get_db),
    lock: SeatLock = Depends(get_seat_lock),
    user: User = Depends(get_required_user),
):
    date_value = Date.fromisoformat(payload.date)
    service = SeatService(db, lock)
    try:
        result = await service.book_seat(seat_id, user.id, date_value, payload.slot)
        return BookResponse(**result)
    except ValueError as e:
        msg = str(e)
        if "已被预约" in msg:
            raise HTTPException(status_code=409, detail={"error": "seat_already_booked", "message": msg})
        if "暂不可用" in msg:
            raise HTTPException(status_code=422, detail={"error": "seat_disabled", "message": msg})
        if "同一时段已有" in msg:
            raise HTTPException(status_code=422, detail={"error": "duplicate_booking", "message": msg})
        if "过去的日期" in msg:
            raise HTTPException(status_code=422, detail={"error": "past_slot", "message": msg})
        raise HTTPException(status_code=422, detail=msg)


@router.get("/appointments", response_model=AppointmentListResponse)
async def list_appointments(
    db: AsyncSession = Depends(get_db),
    lock: SeatLock = Depends(get_seat_lock),
    user: User = Depends(get_required_user),
):
    service = SeatService(db, lock)
    appointments = await service.list_appointments(user.id)
    return AppointmentListResponse(
        appointments=[AppointmentItem(**a) for a in appointments]
    )


@router.post("/appointments/{appointment_id}/cancel", response_model=CancelResponse)
async def cancel_appointment(
    appointment_id: str,
    db: AsyncSession = Depends(get_db),
    lock: SeatLock = Depends(get_seat_lock),
    user: User = Depends(get_required_user),
):
    service = SeatService(db, lock)
    try:
        result = await service.cancel_appointment(appointment_id, user.id)
        return CancelResponse(**result)
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))
```

- [ ] **Step 2: 在 app_main.py 中注册 seat_router**

在 `from backend.router.auth_router import router as auth_router` 后添加：

```python
from backend.router.seat_router import router as seat_router
```

在 `app.include_router(auth_router)` 后添加：

```python
    app.include_router(seat_router)
```

- [ ] **Step 3: Commit**

```bash
cd deep_research_scaffold && git add app/backend/router/seat_router.py app/app_main.py && git commit -m "$(cat <<'EOF'
feat: add seat REST API — list seats, book, cancel, list appointments

Co-Authored-By: Claude Opus 4.6 <noreply@anthropic.com>
EOF
)"
```

---

### Task 15: Seat API 集成测试

**Files:**
- Create: `tests/test_seat_api.py`

- [ ] **Step 1: 编写 test_seat_api.py**

```python
"""Seat API 集成测试 — 座位列表、预约、取消、冲突"""

import pytest
from httpx import ASGITransport, AsyncClient
from app_main import app


async def _create_user_and_login(client, username="seatuser", password="pass123",
                                  display_name="座位测试", student_id="2024001"):
    """辅助函数：注册 + 登录，返回 access_token"""
    await client.post("/api/v1/auth/register", json={
        "username": username,
        "password": password,
        "display_name": display_name,
        "student_id": student_id,
    })
    resp = await client.post("/api/v1/auth/login", json={
        "username": username, "password": password,
    })
    return resp.json()["access_token"]


async def _setup_overrides(db_session, redis_client):
    """注入测试数据库 + fakeredis 到 FastAPI app"""
    from core.database import get_db as _get_db
    from core.lock import SeatLock
    from backend.router.seat_router import get_seat_lock as _get_seat_lock

    async def override_get_db():
        yield db_session

    async def override_get_seat_lock():
        return SeatLock(redis_client)

    app.dependency_overrides[_get_db] = override_get_db
    app.dependency_overrides[_get_seat_lock] = override_get_seat_lock


@pytest.mark.asyncio
async def test_list_seats_empty(db_session, redis_client):
    """无座位数据时返回空列表"""
    await _setup_overrides(db_session, redis_client)

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        token = await _create_user_and_login(client)
        resp = await client.get("/api/v1/seats", headers={"Authorization": f"Bearer {token}"})
        assert resp.status_code == 200
        data = resp.json()
        assert data["seats"] == []

    app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_book_seat_not_found(db_session, redis_client):
    """预约不存在的座位返回 422"""
    await _setup_overrides(db_session, redis_client)

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        token = await _create_user_and_login(client)
        resp = await client.post(
            "/api/v1/seats/nonexistent-id/book",
            json={"date": "2026-07-10", "slot": "morning"},
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 422

    app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_seat_list_and_book_flow(db_session, redis_client):
    """完整预约流程：添加楼层→区域→座位→查列表→预约→查预约→取消"""
    await _setup_overrides(db_session, redis_client)

    # Insert test data — floor, zone, seat
    from models import Floor, Zone, ZoneType, Seat, SeatStatus
    floor = Floor(name="1楼", sort_order=1)
    zone = Zone(name="A区", zone_type=ZoneType.open, sort_order=1, floor=floor)
    seat1 = Seat(seat_number="001", zone=zone)
    seat2 = Seat(seat_number="002", zone=zone)
    db_session.add_all([floor, zone, seat1, seat2])
    await db_session.commit()

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        token = await _create_user_and_login(client)

        # List seats with date/slot — should all be available
        resp = await client.get(
            "/api/v1/seats?date=2026-07-10&slot=morning",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 200
        seats = resp.json()["seats"]
        assert len(seats) == 2
        assert all(s["status"] == "available" for s in seats)

        # Book seat 1
        resp = await client.post(
            f"/api/v1/seats/{seat1.id}/book",
            json={"date": "2026-07-10", "slot": "morning"},
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 200, resp.text
        data = resp.json()
        assert data["seat_id"] == seat1.id
        assert data["date"] == "2026-07-10"
        assert data["slot"] == "morning"

        # List again — seat1 should be booked
        resp = await client.get(
            "/api/v1/seats?date=2026-07-10&slot=morning",
            headers={"Authorization": f"Bearer {token}"},
        )
        seats = resp.json()["seats"]
        s1 = next(s for s in seats if s["seat_id"] == seat1.id)
        assert s1["status"] == "booked"
        assert s1["booked_by_me"] is True

        # Book same seat again — should get 409
        resp = await client.post(
            f"/api/v1/seats/{seat1.id}/book",
            json={"date": "2026-07-10", "slot": "morning"},
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code in (409, 422)

        # List my appointments
        resp = await client.get("/api/v1/appointments", headers={"Authorization": f"Bearer {token}"})
        assert resp.status_code == 200
        appts = resp.json()["appointments"]
        assert len(appts) == 1
        assert appts[0]["seat_id"] == seat1.id

        # Cancel appointment
        appt_id = appts[0]["appointment_id"]
        resp = await client.post(
            f"/api/v1/appointments/{appt_id}/cancel",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 200
        assert resp.json()["status"] == "cancelled"

        # Seat should be available again
        resp = await client.get(
            "/api/v1/seats?date=2026-07-10&slot=morning",
            headers={"Authorization": f"Bearer {token}"},
        )
        s1 = next(s for s in resp.json()["seats"] if s["seat_id"] == seat1.id)
        assert s1["status"] == "available"

    app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_unauthorized_access():
    """未登录访问需要认证的端点返回 401"""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.post("/api/v1/seats/any-id/book", json={
            "date": "2026-07-10", "slot": "morning",
        })
        # 可能返回 401（无token）或 422（无效token处理为匿名）
        assert resp.status_code in (401, 422)

    app.dependency_overrides.clear()
```

- [ ] **Step 2: 运行测试**

```bash
cd deep_research_scaffold && uv run pytest tests/test_seat_api.py -v
```
预期：4 passed

- [ ] **Step 3: Commit**

```bash
cd deep_research_scaffold && git add tests/test_seat_api.py && git commit -m "$(cat <<'EOF'
test: add seat API integration tests — list, book, cancel, conflict

Co-Authored-By: Claude Opus 4.6 <noreply@anthropic.com>
EOF
)"
```

---

### Task 16: 扩展 LLMClient — 预约意图参数提取

**Files:**
- Modify: `app/research_agents/adapters/llm.py`

- [ ] **Step 1: 在 LLMClient Protocol 中添加新方法签名**

在 `LLMClient` Protocol 末尾添加：

```python
    # --- 图书馆预约方法（Phase 2a 新增） ---
    def extract_booking_params(self, query: str) -> dict: ...

    def extract_cancel_params(self, query: str) -> dict: ...
```

- [ ] **Step 2: 在 RuleBasedLLMClient 中实现这两个方法**

在 `stub_message` 方法后面添加：

```python
    def extract_booking_params(self, query: str) -> dict:
        """从用户消息中提取预约参数 — 关键词规则版"""
        lowered = query.lower()
        params = {}

        # 日期识别
        if "今天" in lowered:
            params["date"] = "today"
        elif "明天" in lowered:
            params["date"] = "tomorrow"
        elif "后天" in lowered:
            params["date"] = "day_after_tomorrow"

        # 时段识别
        if any(w in lowered for w in ["上午", "早上"]):
            params["slot"] = "morning"
        elif any(w in lowered for w in ["下午", "中午"]):
            params["slot"] = "afternoon"
        elif any(w in lowered for w in ["晚上", "傍晚"]):
            params["slot"] = "evening"

        # 楼层识别
        for i in range(1, 10):
            if f"{i}楼" in query or f"{i}层" in query:
                params["floor"] = i
                break

        return params

    def extract_cancel_params(self, query: str) -> dict:
        """从用户消息中提取取消参数"""
        # 简单规则：从消息中提取数字作为可能的 appointment ID
        # 实际更复杂的场景由 reservation_subgraph 的 understand_booking 节点处理
        return {"query": query}

    def format_reservation_response(self, intent: str, result: dict) -> str:
        """格式化预约操作结果为自然语言回复"""
        if intent == "book_seat":
            return (
                f"预约成功！座位：{result.get('floor_name', '')}-"
                f"{result.get('zone_name', '')}-{result.get('seat_number', '')}，"
                f"日期：{result.get('date', '')}，时段：{result.get('slot', '')}"
            )
        elif intent == "query_appointment":
            appts = result.get("appointments", [])
            if not appts:
                return "您目前没有预约记录。"
            lines = ["您的预约记录："]
            for a in appts:
                lines.append(
                    f"- {a['floor_name']}-{a['zone_name']}-{a['seat_number']} "
                    f"({a['date']} {'上午' if a['slot'] == 'morning' else '下午' if a['slot'] == 'afternoon' else '晚上'}) "
                    f"[{a['appointment_id']}]"
                )
            return "\n".join(lines)
        elif intent == "cancel_appointment":
            return f"预约已取消（{result.get('appointment_id', '')}）。"
        return "操作完成。"
```

- [ ] **Step 3: 验证 import 正常**

```bash
cd deep_research_scaffold && uv run python -c "
import sys; sys.path.insert(0, 'app')
from research_agents.adapters.llm import RuleBasedLLMClient
c = RuleBasedLLMClient()
assert 'date' in c.extract_booking_params('帮我预约明天上午3楼的座位')
assert 'tomorrow' == c.extract_booking_params('帮我预约明天上午3楼的座位')['date']
print('OK')
"
```

- [ ] **Step 4: Commit**

```bash
cd deep_research_scaffold && git add app/research_agents/adapters/llm.py && git commit -m "$(cat <<'EOF'
feat: extend LLMClient with booking param extraction and reservation response formatting

Co-Authored-By: Claude Opus 4.6 <noreply@anthropic.com>
EOF
)"
```

---

### Task 17: Agent 层 — reservation 子图节点

**Files:**
- Modify: `app/agents/nodes.py`

- [ ] **Step 1: 在 nodes.py 中新增 reservation 子图节点**

在 `LibraryNodeContext` dataclass 中追加字段（替换原有定义）：

```python
@dataclass(frozen=True)
class LibraryNodeContext:
    """节点依赖注入容器"""

    config: ChatConfig
    llm: LLMClient
    retriever: Retriever
    book_lookup: Retriever
    auth_service: object | None = None    # Phase 2a: AuthService
    seat_service: object | None = None    # Phase 2a: SeatService
```

在文件末尾追加 reservation 子图节点函数：

```python
# --- Reservation 子图节点（Phase 2a） ---

def reservation_useerstand_node(state: LibraryState, context: LibraryNodeContext) -> dict:
    """预约子图入口 — 解析用户消息，提取结构化参数"""
    intent = state["intent"]
    query = state["query"]

    if intent == "book_seat":
        params = context.llm.extract_booking_params(query)
    elif intent == "cancel_appointment":
        params = context.llm.extract_cancel_params(query)
    else:
        params = {"query": query}

    return {"context": {"intent": intent, "reservation_params": params}}


def reservation_book_node(state: LibraryState, context: LibraryNodeContext) -> dict:
    """预约座位节点 — 返回指引（实际预约通过 REST API）"""
    params = state.get("context", {}).get("reservation_params", {})
    # Agent 层提取参数后返回自然语言引导，实际 booking 走 REST API
    date_hint = params.get("date", "请指定日期")
    slot_hint = params.get("slot", "请选择时段")
    floor_hint = f"{params['floor']}楼" if params.get("floor") else "请指定楼层"

    response = (
        f"根据您的需求：{floor_hint}，{date_hint}，{slot_hint}时段。"
        f"请在座位列表中选择具体座位进行预约。"
    )
    return {"response": response, "sources": []}


def reservation_query_node(state: LibraryState, context: LibraryNodeContext) -> dict:
    """查询预约节点 — 返回指引"""
    response = "请在「我的预约」页面查看您的预约记录。"
    return {"response": response, "sources": []}


def reservation_cancel_node(state: LibraryState, context: LibraryNodeContext) -> dict:
    """取消预约节点 — 返回指引"""
    response = "请在「我的预约」中找到对应预约，点击取消即可。"
    return {"response": response, "sources": []}


def reservation_format_node(state: LibraryState, context: LibraryNodeContext) -> dict:
    """格式化预约结果"""
    response = state.get("response", "")
    return {"response": response, "sources": state.get("sources", [])}
```

注意：Phase 2a 的 Agent 预约节点返回引导性回复，实际的 booking/cancel 通过 REST API `/api/v1/seats/{id}/book` 和 `/api/v1/appointments/{id}/cancel` 完成。后续 Phase 2b 可以直接在 Agent 节点中调用 `seat_service` 实现端到端对话预约。

- [ ] **Step 2: Commit**

```bash
cd deep_research_scaffold && git add app/agents/nodes.py && git commit -m "$(cat <<'EOF'
feat: add reservation subgraph nodes — NL param extraction

Co-Authored-By: Claude Opus 4.6 <noreply@anthropic.com>
EOF
)"
```

---

### Task 18: Agent 层 — reservation_subgraph 集成到主图

**Files:**
- Modify: `app/agents/graph.py`

- [ ] **Step 1: 修改 graph.py — 添加 reservation_subgraph 构建函数 + 替换 stub**

替换所有 import 和 graph 构建逻辑：

在 imports 中添加 reservation 节点引用（更新已有 import）：

```python
from .nodes import (
    LibraryNodeContext,
    book_lookup_node,
    direct_answer_node,
    format_response_node,
    intent_classifier_node,
    policy_retrieval_node,
    profile_stub_node,
    recommend_retrieve_node,
    reservation_book_node,
    reservation_cancel_node,
    reservation_format_node,
    reservation_query_node,
    reservation_understand_node,
    retrieval_understand_node,
)
```

在 `build_library_graph` 中将 `reservation_stub` 替换为 `reservation_subgraph`：

```python
    graph.add_node("reservation_subgraph", _build_reservation_subgraph(context))
```

条件边映射改为：

```python
    graph.add_conditional_edges(
        "intent_classifier",
        _route_by_subgraph,
        {
            "retrieval": "retrieval_subgraph",
            "reservation": "reservation_subgraph",   # 改为子图
            "profile": "profile_stub",
            "direct": "direct_answer",
        },
    )
    graph.add_edge("reservation_subgraph", END)
```

在文件末尾添加子图构建函数：

```python
def _build_reservation_subgraph(context: LibraryNodeContext):
    """构建预约子图：understand → book/query/cancel → format"""
    sub = StateGraph(LibraryState)

    sub.add_node("understand_booking", lambda s: reservation_understand_node(s, context))
    sub.add_node("book_seat", lambda s: reservation_book_node(s, context))
    sub.add_node("query_appointments", lambda s: reservation_query_node(s, context))
    sub.add_node("cancel_appointment", lambda s: reservation_cancel_node(s, context))
    sub.add_node("format_response", lambda s: reservation_format_node(s, context))

    sub.add_edge(START, "understand_booking")
    sub.add_conditional_edges(
        "understand_booking",
        _route_reservation_branch,
        {
            "book": "book_seat",
            "query": "query_appointments",
            "cancel": "cancel_appointment",
        },
    )
    sub.add_edge("book_seat", "format_response")
    sub.add_edge("query_appointments", "format_response")
    sub.add_edge("cancel_appointment", "format_response")
    sub.add_edge("format_response", END)

    return sub.compile()


def _route_reservation_branch(state: LibraryState) -> str:
    """预约子图路由：根据意图选择对应节点"""
    intent = state.get("intent", "book_seat")
    mapping = {
        "book_seat": "book",
        "query_appointment": "query",
        "cancel_appointment": "cancel",
    }
    return mapping.get(intent, "book")
```

- [ ] **Step 2: 验证 graph 构建无错误**

```bash
cd deep_research_scaffold && uv run python -c "
import sys; sys.path.insert(0, 'app')
from agents.config import ChatConfig
from agents.graph import build_library_graph
from agents.nodes import LibraryNodeContext
from research_agents.adapters.llm import RuleBasedLLMClient
from agents.retrieval.protocol import StubRetriever

ctx = LibraryNodeContext(
    config=ChatConfig(),
    llm=RuleBasedLLMClient(),
    retriever=StubRetriever(),
    book_lookup=StubRetriever(),
)
graph = build_library_graph(ctx)
print('Graph built OK')
"
```

- [ ] **Step 3: Commit**

```bash
cd deep_research_scaffold && git add app/agents/graph.py && git commit -m "$(cat <<'EOF'
feat: upgrade reservation stub to full reservation_subgraph

Co-Authored-By: Claude Opus 4.6 <noreply@anthropic.com>
EOF
)"
```

---

### Task 19: Agent 层集成测试 — reservation_subgraph

**Files:**
- Modify: `tests/test_library_graph.py`

- [ ] **Step 1: 在 test_library_graph.py 中更新已有测试**

`test_stub_returns_placeholder` 测试预期需要改为新行为 — 不再返回"开发中"。

替换 `test_stub_returns_placeholder`：

```python
def test_reservation_book_returns_guidance(app):
    """预约节点返回引导信息而非开发中提示"""
    state = create_initial_library_state(query="我要预约座位")
    result = app.invoke(state)
    assert "开发中" not in result["response"]
    assert len(result["response"]) > 0


def test_reservation_cancel_returns_guidance(app):
    state = create_initial_library_state(query="取消我的预约")
    result = app.invoke(state)
    assert "开发中" not in result["response"]
    assert len(result["response"]) > 0


def test_reservation_query_returns_guidance(app):
    state = create_initial_library_state(query="我的预约记录")
    result = app.invoke(state)
    assert "开发中" not in result["response"]
    assert len(result["response"]) > 0
```

- [ ] **Step 2: 运行全部 Agent 测试**

```bash
cd deep_research_scaffold && uv run pytest tests/test_library_graph.py tests/test_intent_classification.py -v
```
预期：全部通过（原来的 stub 占位测试变为 reservation 引导测试）

- [ ] **Step 3: Commit**

```bash
cd deep_research_scaffold && git add tests/test_library_graph.py && git commit -m "$(cat <<'EOF'
test: update agent tests for reservation_subgraph

Co-Authored-By: Claude Opus 4.6 <noreply@anthropic.com>
EOF
)"
```

---

### Task 20: 最终集成验证

**Files:**
- Modify: `tests/test_chat_api.py` (扩展 E2E)

- [ ] **Step 1: 运行全部测试**

```bash
cd deep_research_scaffold && uv run pytest tests/ -v
```

- [ ] **Step 2: 验证全部通过，确认数量**

预期：之前 32 tests + 新增约 30 tests = ~62 tests 全部通过。

- [ ] **Step 3: 扩展 E2E 测试 — 添加预约对话测试**

在 test_chat_api.py 末尾添加：

```python
def test_chat_booking_intent_no_longer_stub():
    """预约相关意图不再返回 '开发中'"""
    resp = client.post("/api/v1/chat", json={"query": "我要预约座位"})
    assert resp.status_code == 200
    data = resp.json()
    assert "开发中" not in data["response"]


def test_chat_cancel_intent_no_longer_stub():
    resp = client.post("/api/v1/chat", json={"query": "取消我的预约"})
    assert resp.status_code == 200
    data = resp.json()
    assert "开发中" not in data["response"]
```

- [ ] **Step 4: 再次运行全部测试**

```bash
cd deep_research_scaffold && uv run pytest tests/ -v
```
预期：全部通过

- [ ] **Step 5: 提交最终更改**

```bash
cd deep_research_scaffold && git add tests/test_chat_api.py && git commit -m "$(cat <<'EOF'
test: add E2E verification for reservation intent (no longer stub)

Co-Authored-By: Claude Opus 4.6 <noreply@anthropic.com>
EOF
)"
```

- [ ] **Step 6: 查看最终 git log**

```bash
cd deep_research_scaffold && git log --oneline -12
```

---

### Task 21: 推送

- [ ] **Step 1: 推送到 dev 分支**

```bash
cd deep_research_scaffold && git push origin dev
```

---

## 依赖顺序

```
Task 1 (deps) ──→ Task 2 (core infra) ──→ Task 3 (models) ──→ Task 4 (Alembic)
                                                                    ↓
Task 5 (security) ──→ Task 6 (deps) ──→ Task 8 (auth schemas) ──→ Task 9 (auth service) ──→ Task 10 (auth router) ──→ Task 11 (auth tests)
                                                                                                                              ↓
Task 7 (lock) ──→ Task 12 (seat schemas) ──→ Task 13 (seat service) ──→ Task 14 (seat router) ──→ Task 15 (seat tests)
                                                                                                          ↓
Task 16 (LLM extend) ──→ Task 17 (reservation nodes) ──→ Task 18 (reservation graph) ──→ Task 19 (agent tests)
                                                                                              ↓
                                                                                    Task 20 (final verification)
                                                                                              ↓
                                                                                    Task 21 (push)
```

可以并行执行：
- Task 5 (security) 和 Task 3-4 (models/migration) 并行
- Task 7 (lock) 和 Task 8-11 (auth) 并行
- Task 16 (LLM) 可以在 Task 17 之前的任意时间做
