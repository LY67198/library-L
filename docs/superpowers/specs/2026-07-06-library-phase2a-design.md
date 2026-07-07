# Phase 2a: 用户系统 + 座位预约 — 设计文档

## 概述

Phase 2a 实现用户认证和座位预约的核心闭环：注册 → 登录 → 选座 → 预约 → 取消。Celery 超时释放和座位可视化前端推后到 Phase 2b。

## 技术决策摘要

| 模块 | 决策 |
|------|------|
| 数据库 | SQLAlchemy 2.0 async + asyncpg + Alembic 迁移 |
| 认证 | JWT（access 30min + refresh 7day），python-jose + passlib[bcrypt] |
| 座位层级 | 楼层 → 区域 → 座位号（如 2楼-A区-032） |
| 预约规则 | 按时段：上午 8-12 / 下午 13-17 / 晚上 18-22 |
| 并发控制 | Redis `SET NX EX` + PostgreSQL `version` 乐观锁双重保障 |
| 超时释放 | 懒清理——查询时检查过期释放，不引入 Celery |
| Agent | `reservation_stub` → 真实 `reservation_subgraph` |
| 并发模型 | async/await 全面异步，FastAPI async handler + async SQLAlchemy session |

## 数据模型

```
Floor (楼层)
  id (PK), name (如 "1楼"), sort_order
  1 ── N → Zone

Zone (区域)
  id (PK), floor_id (FK→Floor), name (如 "A区/自习区"),
  zone_type (enum: open/room/electronic), sort_order
  1 ── N → Seat

Seat (座位)
  id (PK/UUID), zone_id (FK→Zone), seat_number (如 "032"),
  status (enum: available/disabled, 默认 available)
  1 ── N → SeatTimeSlot

SeatTimeSlot (座位时段占用 — 核心并发表)
  id (PK/UUID), seat_id (FK→Seat), date, slot (enum: morning/afternoon/evening),
  user_id (FK→User), booked_at
  version (int, 乐观锁)
  UNIQUE (seat_id, date, slot)  ← 防止双约

User (用户)
  id (PK/UUID), username (UNIQUE), password_hash, display_name,
  student_id (UNIQUE), is_active (默认 true), created_at

Appointment (预约记录 — 操作流水)
  id (PK/UUID), user_id (FK→User), seat_id (FK→Seat),
  date, slot,
  status (enum: booked/checked_in/cancelled/expired),
  created_at, updated_at
```

**核心关系**：`SeatTimeSlot` 是并发竞争的焦点（UNIQUE 约束 + version），`Appointment` 是操作流水，业务逻辑需保证两者一致。

## 座位状态模型

| 状态 | 含义 | 作用域 |
|------|------|--------|
| `available` | 可预约 | Seat.status |
| `disabled` | 维护/关闭 | Seat.status |
| `booked` | 已预约（含已签到） | SeatTimeSlot（时段级） |

查询可用座位时：`Seat.status = available AND 该时段无 SeatTimeSlot 记录`。

## API 设计

### Auth

| 方法 | 路径 | 说明 | 认证 |
|------|------|------|------|
| POST | `/api/v1/auth/register` | 注册 | - |
| POST | `/api/v1/auth/login` | 登录 | - |
| POST | `/api/v1/auth/refresh` | 刷新 token | - |
| GET | `/api/v1/auth/me` | 当前用户 | Bearer |

请求/响应：

```python
# POST /api/v1/auth/register
class RegisterRequest(BaseModel):
    username: str           # 4-32 chars
    password: str           # 8-128 chars
    display_name: str       # 1-32 chars
    student_id: str         # 学号，唯一

class RegisterResponse(BaseModel):
    user_id: str
    username: str

# POST /api/v1/auth/login
class LoginRequest(BaseModel):
    username: str
    password: str

class LoginResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"

# POST /api/v1/auth/refresh
class RefreshRequest(BaseModel):
    refresh_token: str

class RefreshResponse(BaseModel):
    access_token: str

# GET /api/v1/auth/me
class UserProfile(BaseModel):
    user_id: str
    username: str
    display_name: str
    student_id: str
```

### 座位

| 方法 | 路径 | 说明 | 认证 |
|------|------|------|------|
| GET | `/api/v1/seats` | 座位列表 | Bearer（可选） |
| POST | `/api/v1/seats/{id}/book` | 预约座位 | Bearer |
| GET | `/api/v1/appointments` | 我的预约 | Bearer |
| POST | `/api/v1/appointments/{id}/cancel` | 取消预约 | Bearer |

请求/响应：

```python
# GET /api/v1/seats?floor_id=1&zone_id=2&date=2026-07-06&slot=morning
class SeatItem(BaseModel):
    seat_id: str
    floor_name: str
    zone_name: str
    seat_number: str
    status: str           # available / booked
    booked_by_me: bool    # 是否是我约的

class SeatListResponse(BaseModel):
    seats: list[SeatItem]

# POST /api/v1/seats/{id}/book
class BookRequest(BaseModel):
    date: str             # YYYY-MM-DD
    slot: str             # morning/afternoon/evening

class BookResponse(BaseModel):
    appointment_id: str
    seat_id: str
    floor_name: str
    zone_name: str
    seat_number: str
    date: str
    slot: str

# GET /api/v1/appointments
class AppointmentItem(BaseModel):
    appointment_id: str
    seat_id: str
    floor_name: str
    zone_name: str
    seat_number: str
    date: str
    slot: str
    status: str

# POST /api/v1/appointments/{id}/cancel
class CancelResponse(BaseModel):
    appointment_id: str
    status: str           # cancelled
```

### 错误码

| HTTP | error | 说明 |
|------|-------|------|
| 409 | `seat_already_booked` | 座位已被他人预约 |
| 422 | `seat_disabled` | 座位维护中 |
| 422 | `duplicate_booking` | 同一时段已预约其他座位 |
| 422 | `past_slot` | 不能预约已过去的时段 |
| 401 | `invalid_token` | Token 无效/过期 |

## Redis 分布式锁

```python
# app/core/lock.py

class SeatLock:
    """座位预约分布式锁。仅用于预约操作窗口的快速抢占，持久状态靠 PG。"""

    def __init__(self, redis_client):
        self.redis = redis_client

    async def acquire(self, seat_id: str, date: str, slot: str,
                      user_id: str, ttl: int = 30) -> bool:
        key = f"seat:{seat_id}:{date}:{slot}"
        return await self.redis.set(key, user_id, nx=True, ex=ttl)

    async def release(self, seat_id: str, date: str, slot: str) -> None:
        key = f"seat:{seat_id}:{date}:{slot}"
        await self.redis.delete(key)
```

**双重保障流程：**

```
POST /seats/{id}/book
  → Redis SET seat:{id}:{date}:{slot} NX EX 30  (第一层，快速失败)
  → 失败？→ HTTP 409 seat_already_booked
  → 成功
  → PG BEGIN
      → INSERT INTO seat_time_slots (seat_id, date, slot, user_id)
      → UNIQUE(seat_id, date, slot) 冲突？→ ROLLBACK + Redis DEL → HTTP 409
      → INSERT INTO appointments (user_id, seat_id, date, slot, status="booked")
      → COMMIT
```

- **第一层 Redis**：毫秒级抢占，挡掉 99% 并发冲突
- **第二层 PG UNIQUE 约束**：Redis 网络抖动 / 锁刚过期等边界场景的最后防线
- `version` 字段预留在 `SeatTimeSlot`，后续 Phase 2b/3 用于签到/修改路径的乐观锁，本次预约插入路径靠 UNIQUE 即可

## LangGraph 改造

Phase 1 中 `reservation_stub_node` → Phase 2a 替换为 `reservation_subgraph`：

```
reservation_subgraph:
  START
    → understand_booking       (解析 NL→结构化：日期/时段/座位号)
      → book_seat_node         (预约流程)
      → query_appt_node        (查询我的预约)
      → cancel_appt_node       (取消预约)
    → format_reservation_response
    → END
```

子图内部路由根据 `intent`：`book_seat` → book_seat_node，`query_appointment` → query_appt_node，`cancel_appointment` → cancel_appt_node。

`LibraryNodeContext` 新增依赖：

```python
@dataclass(frozen=True)
class LibraryNodeContext:
    config: ChatConfig
    llm: LLMClient
    retriever: Retriever
    book_lookup: Retriever
    auth_service: AuthService       # 新增
    seat_service: SeatService       # 新增
```

需要从 nodes.py 解析结构化参数。`RuleBasedLLMClient` 新增方法：

```python
def extract_booking_params(self, query: str) -> dict:
    """从用户消息中提取 date/slot/floor/zone/seat 参数"""
    ...

def extract_cancel_params(self, query: str) -> dict:
    """从用户消息中提取预约 ID"""
    ...
```

## 项目结构

```
app/
├── core/                          ← 新增
│   ├── __init__.py
│   ├── database.py                # async SQLAlchemy engine + session factory
│   ├── security.py                # JWT 签发/验证 + password hashing
│   ├── lock.py                    # SeatLock (Redis)
│   └── deps.py                    # FastAPI Depends: get_db, get_current_user
├── models/                        ← 新增
│   ├── __init__.py
│   ├── base.py                    # SQLAlchemy DeclarativeBase
│   ├── user.py
│   ├── floor.py
│   ├── zone.py
│   ├── seat.py
│   ├── seat_time_slot.py
│   └── appointment.py
├── agents/                        ← 修改
│   ├── config.py                  # ChatConfig 扩展 Redis DB session 等
│   ├── graph.py                   # reservation_stub → reservation_subgraph
│   ├── nodes.py                   # 新增 reservation 节点 + 扩展 context
│   └── ...
├── backend/
│   ├── router/
│   │   ├── auth_router.py         ← 新增
│   │   └── seat_router.py         ← 新增
│   ├── schemas/
│   │   ├── auth.py                ← 新增
│   │   └── seat.py                ← 新增
│   └── service/
│       ├── auth_service.py        ← 新增
│       └── seat_service.py        ← 新增
├── app_main.py                    # 注册 auth_router + seat_router
tests/
├── test_auth_api.py               ← 新增
├── test_seat_api.py               ← 新增
├── test_library_graph.py          # 扩展：reservation 子图测试
├── test_seat_lock.py              ← 新增
└── conftest.py                    # 扩展：fakeredis + SQLite fixtures
migrations/                        ← Alembic 初始化
```

## 依赖新增

```toml
# pyproject.toml
"sqlalchemy[asyncio]>=2.0",
"asyncpg>=0.30",
"alembic>=1.14",
"python-jose[cryptography]>=3.3",
"passlib[bcrypt]>=1.7",
"redis[hiredis]>=5.0",
```

dev：

```toml
"fakeredis[lua]>=2.22",
"httpx>=0.28",         # TestClient 的 async transport
"aiosqlite>=0.20",     # 集成测试用 SQLite
```

## 测试策略

| 层级 | 数量 | 测什么 | 依赖 |
|------|------|--------|------|
| 单元 | 15+ | security 签发/验证、lock 加锁/释放、auth/seat service 逻辑 | 全部 mock |
| 集成 | 10+ | Auth API 注册→登录→refresh→me，Seat API 筛选→预约→取消→冲突 | TestClient + fakeredis + aiosqlite |
| Agent | 8+ | reservation_subgraph 3 意图路由 + 错误降级 + stub→real | Mock service |
| E2E | 3-5 | 完整对话：登录→查座位→预约→查预约→取消 | TestClient + fakeredis + aiosqlite |

**明确不测：** Redis 网络分区、PG 真实并发冲突（单元测 mock 覆盖逻辑）、Vue 组件渲染、Celery（Phase 2b）。

## 超时释放（懒清理）

Phase 2a 不引入 Celery。时段开始 30 分钟后未签到的预约，在以下时机被懒清理：

1. `GET /api/v1/seats` — 查询座位列表时检查并释放过期未签到的 `SeatTimeSlot`
2. `POST /api/v1/seats/{id}/book` — 预约前检查并清理目标座位过期占用

清理逻辑：删除过期未签到的 `SeatTimeSlot` 和对应的 `Appointment`（`date = today AND slot = current AND status = "booked" AND booked_at < slot_start + 30min`），同步释放 Redis key，Appointment 状态更新为 `expired`。

## 时序注意事项

- 座位预约时间以服务器时间（UTC）为准，API 接受本地日期，内部归一化
- access_token 30 分钟过期，refresh_token 7 天过期
- Redis key TTL 30 秒仅覆盖抢占窗口，预约成功后 key 保留至时段结束
