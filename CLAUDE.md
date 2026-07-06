# 图书馆智能服务系统 — 项目进度

## 项目概述

基于 `deep_research_scaffold`（FastAPI + LangGraph 脚手架）的图书馆智能服务系统。Phase 1 聚焦 AI 智能问答 + 馆藏检索，Phase 2a 实现用户认证 + 座位预约闭环，Phase 2b 实现座位可视化前端，Phase 2c 实现 Celery 超时释放。

## 仓库

- GitHub: https://github.com/LY67198/library-L.git
- Gitee: https://gitee.com/lingering-yesterday/library-l.git
- 分支: `main`（主分支）、`dev`（开发分支）

## 当前进度

**已完成:**

- [x] 脚手架导入（`deep_research_scaffold` 全部文件）
- [x] 清理脚手架冗余文件（`LEARNING_PATH.md`、`SCAFFOLD.md`、`*.egg-info/`）
- [x] Phase 1 设计文档 → `docs/superpowers/specs/2026-07-06-library-qa-design.md`
- [x] Phase 1 实现计划 → `docs/superpowers/plans/2026-07-06-library-qa-phase1.md`
- [x] Phase 1 代码实现（32 tests passed）
- [x] README 重写为图书馆项目说明
- [x] `.env.example` 完善（DeepSeek + MiniMax + Qwen 嵌入/重排序）
- [x] Docker 部署配置

**Phase 2a — 已完成:**

- [x] 设计文档 → `docs/superpowers/specs/2026-07-06-library-phase2a-design.md`
- [x] 实现计划 → `docs/superpowers/plans/2026-07-06-library-phase2a.md`
- [x] 依赖安装（SQLAlchemy async, asyncpg, Alembic, JWT, bcrypt, Redis）
- [x] 核心基础设施（`app/core/` — database, security, deps, lock）
- [x] 数据模型（`app/models/` — User, Floor, Zone, Seat, SeatTimeSlot, Appointment）
- [x] Alembic 迁移初始化
- [x] Auth/Seat Schemas
- [x] 单元测试：security (5) + lock (5) = 10 tests passed
- [x] Auth/Seat Service + Router → 注册/登录/refresh/me + 座位列表/预约/取消/查预约
- [x] Agent 层 reservation_subgraph → 5 节点子图替换 stub
- [x] 集成测试 + E2E → 56 tests passed

**Phase 2b — 座位可视化前端 — 已完成:**

- [x] 设计文档 → `docs/superpowers/specs/2026-07-06-library-phase2b-design.md`
- [x] 实现计划 → `docs/superpowers/plans/2026-07-06-library-phase2b.md`
- [x] 后端：`SeatItem` 增加 `floor_id`/`zone_id` 字段
- [x] 后端：`GET /api/v1/seats` 改为可选认证（匿名可浏览）
- [x] 前端：vue-router + Element Plus 应用壳搭建
- [x] 前端：API 层（client, seats, auth）+ useAuth 组合式函数
- [x] 前端：登录页面 + 座位可视化组件（TimeSlotPicker, ZoneChips, SeatCard, SeatGrid, SeatLegend, BookingConfirmDialog）
- [x] 前端：SeatDashboard 主页面 + HomeView 导航入口
- [x] 前端：`npm run build` 构建成功
- [x] 后端：57 tests passed（含新增匿名访问测试）

**Phase 2c — Celery 超时释放 — 已完成:**

- [x] 设计文档 → `docs/superpowers/specs/2026-07-06-library-phase2c-design.md`
- [x] 实现计划 → `docs/superpowers/plans/2026-07-06-library-phase2c.md`
- [x] 新建 `app/core/cleanup.py` — 释放逾期座位逻辑，Celery Beat 和懒清理共用
- [x] 新建 `app/tasks/` — Celery 任务定义（`celery_app.py` + `cleanup.py`），Celery Beat 每 5 分钟轮询释放
- [x] `pyproject.toml` 新增 `celery` 依赖
- [x] Docker Compose 新增 `celery_worker` + `celery_beat` 服务
- [x] 10 个单元测试（`tests/test_cleanup.py`），mock 检测阈值
- [x] 67 tests passed（新增 10 test_cleanup.py）

## LLM / 模型配置

| 厂商 | 用途 | 模型 |
|------|------|------|
| DeepSeek | 对话 | `deepseek-v4-flash` |
| MiniMax | 对话 | `MiniMax-M3` |
| Qwen (DashScope) | 嵌入 | `text-embedding-v2` (1024d) |
| Qwen (DashScope) | 重排序 | `qwen3-rerank` |

API Key 都在 `.env` 中配置（已 gitignore），模板见 `.env.example`。

## 核心设计决策

| 决策 | 选择 |
|------|------|
| Agent 编排 | LangGraph 显式编排，1 主图 + 2 子图（retrieval + reservation） |
| LLM | 当前 `RuleBasedLLMClient` 扩展 9 分类，后续接入 MiniMax（对话）、Qwen（嵌入/重排序） |
| 检索 | `Retriever` Protocol 插件化 — `ChromaDBRetriever` + `SQLBookLookup`（当前用 StubRetriever） |
| State | 新包 `agents/`，不侵入 `research_agents/` |
| 前端 | 脚手架 Vue 3 前端重写为对话界面 |
| 部署 | Docker Compose（FastAPI + PostgreSQL + Redis） |
| 依赖管理 | `uv`（pyproject.toml） |
| 认证 | JWT（access 30min + refresh 7day），python-jose + bcrypt |
| 并发控制 | Redis `SET NX EX` + PostgreSQL UNIQUE 约束双重保障 |
| 数据库 | SQLAlchemy 2.0 async + asyncpg + Alembic |
| 座位层级 | 楼层 → 区域 → 座位号 |
| 预约规则 | 按时段：上午 8-12 / 下午 13-17 / 晚上 18-22 |

## 9 种用户意图

`search_book` `recommend_book` `policy_query` `book_seat` `query_appointment` `cancel_appointment` `profile_query` `greeting` `other`

## 项目结构

```
app/
├── core/                    ← Phase 2a 新建
│   ├── database.py          ← async SQLAlchemy engine + session
│   ├── security.py          ← JWT 签发/验证 + bcrypt
│   ├── deps.py              ← FastAPI Depends: get_db, get_current_user
│   ├── lock.py              ← Redis 分布式锁 (SeatLock)
│   └── cleanup.py           ← Phase 2c: 释放逾期座位（Celery + 懒清理共用）
├── models/                  ← Phase 2a 新建
│   ├── base.py              ← SQLAlchemy DeclarativeBase
│   ├── user.py              ← User
│   ├── floor.py             ← Floor
│   ├── zone.py              ← Zone
│   ├── seat.py              ← Seat
│   ├── seat_time_slot.py    ← SeatTimeSlot (核心并发表)
│   └── appointment.py       ← Appointment (操作流水)
├── tasks/                   ← Phase 2c 新建
│   ├── celery_app.py        ← Celery 实例 + Beat 调度配置
│   └── cleanup.py           ← Celery 任务（release_expired_slots）
├── agents/                  ← Phase 1 新建
│   ├── state.py             ← LibraryState
│   ├── graph.py             ← 主图 + retrieval 子图
│   ├── nodes.py             ← 9 节点 + LibraryNodeContext
│   ├── config.py            ← ChatConfig
│   └── retrieval/
│       ├── protocol.py      ← Retriever Protocol + StubRetriever
│       ├── chroma_retriever.py
│       └── sql_book_lookup.py
├── research_agents/         ← 脚手架原有（llm.py 扩展）
│   └── adapters/llm.py      ← LLMClient Protocol + RuleBasedLLMClient（9 分类）
└── backend/
    ├── router/
    │   ├── chat_router.py   ← Phase 1
    │   ├── book_router.py   ← Phase 1
    │   ├── auth_router.py   ← Phase 2a ✅
    │   └── seat_router.py   ← Phase 2a ✅
    ├── schemas/
    │   ├── chat.py          ← Phase 1
    │   ├── auth.py          ← Phase 2a
    │   └── seat.py          ← Phase 2a
    └── service/
        ├── chat_service.py  ← Phase 1
        ├── auth_service.py  ← Phase 2a ✅
        └── seat_service.py  ← Phase 2a ✅
tests/
├── test_intent_classification.py  ← 12 tests
├── test_library_graph.py          ← 14 tests
├── test_chat_api.py               ← 6 tests
├── test_security.py               ← 5 tests (Phase 2a)
├── test_lock.py                   ← 5 tests (Phase 2a)
├── test_auth_api.py               ← Phase 2a ✅
├── test_seat_api.py               ← Phase 2a + Phase 2b（匿名访问测试）
└── test_cleanup.py                ← 10 tests (Phase 2c)
```

**前端结构（Phase 2b 新增）:**

```
front/src/
├── main.ts                          ← ElementPlus + Router 注册
├── App.vue                          ← <router-view /> 路由壳
├── api/
│   ├── client.ts                    ← fetch 封装 + token 注入
│   ├── seats.ts                     ← 座位 API（fetchSeats, bookSeat）
│   └── auth.ts                      ← 认证 API（login, fetchMe）
├── composables/
│   └── useAuth.ts                   ← 全局认证状态管理
├── router/
│   └── index.ts                     ← / → Home, /seats → Dashboard, /login
├── views/
│   ├── HomeView.vue                 ← 聊天界面（Phase 1 迁移）
│   ├── LoginView.vue                ← 登录页面
│   └── SeatDashboard.vue            ← 座位预约主页面
└── components/
    ├── TimeSlotPicker.vue           ← 时段选择（上午/下午/晚上）
    ├── ZoneChips.vue                ← 区域 Tag 筛选
    ├── SeatCard.vue                 ← 座位色块（绿/红/蓝/灰）
    ├── SeatGrid.vue                 ← 8 列座位网格
    ├── SeatLegend.vue               ← 颜色图例
    └── BookingConfirmDialog.vue     ← 预约确认弹窗
```

## 下一步

**后续 Phase:**
1. 实现真实 LLMClient（对话用 MiniMax/DeepSeek，嵌入/重排序用 Qwen）
2. 初始化 ChromaDB 知识库 + PostgreSQL 图书数据
3. Phase 3：读者画像 + 知识库管理 + MCP Server + 可观测性

## 断点续接 — 2026-07-06（RESTful 重构 ✅ 已完成）

**当前状态:** Phase 2c Celery 超时释放已完成。RESTful 规范化重构已完成，67 tests passed + 前端构建通过。

### RESTful 重构 — 已全部完成

- [x] **Seat schemas**: `BookResponse`→`BookingResponse`，`SeatListResponse`/`AppointmentListResponse` 新增 `total`/`offset`/`limit` 分页字段
- [x] **seat_router**:
  - `POST /seats/{id}/book` → `POST /seats/{id}/bookings`（动词→名词）
  - `POST /appointments/{id}/cancel` → `DELETE /appointments/{id}`（204 No Content）
  - `GET /seats` 和 `GET /appointments` 新增 `offset`/`limit` 查询参数
  - router 去掉硬编码 prefix，每个 route 自带完整路径
- [x] **book_router**: `GET /books` 返回格式从 `list` 改为 `{"items": [...], "total", "offset", "limit"}`
- [x] **测试更新**: `test_seat_api.py` URL 同步更新（`/book`→`/bookings`，cancel 改用 `.delete()`，断言 204）
- [x] **test_chat_api.py**: book 响应断言改为 `"items" in data`
- [x] **前端 `api/client.ts`**: 新增 `apiDelete()` 函数
- [x] **前端 `api/seats.ts`**: `bookSeat` URL→`/bookings`，新增 `cancelAppointment()`，fetchSeats 支持 `offset`/`limit`
- [x] **全量测试**: 67 tests passed
- [x] **前端构建**: `npm run build` 通过

### 新的 API 一览

| 方法 | URL | 说明 |
|------|-----|------|
| GET | `/api/v1/seats` | 座位列表（+offset/limit 分页） |
| POST | `/api/v1/seats/{id}/bookings` | 预约座位 |
| GET | `/api/v1/appointments` | 我的预约（+offset/limit 分页） |
| DELETE | `/api/v1/appointments/{id}` | 取消预约 |

**已实现（全部）:**
- Auth: POST /api/v1/auth/register, login, refresh, GET /me
- Seats: GET /api/v1/seats（可选认证）, POST /seats/{id}/bookings, GET /appointments, DELETE /appointments/{id}
- Agent: reservation_subgraph（5 节点）替换 reservation_stub，返回引导性回复
- LLM: extract_booking_params, extract_cancel_params, format_reservation_response
- 前端: Vue 3 + Element Plus 座位可视化（网格浏览 → 时段筛选 → 一键预约）
- Phase 2c: `app/core/cleanup.py` — `cleanup_expired_slots()` 清理逻辑
- Phase 2c: `app/tasks/` — Celery 应用 + 任务 + Beat 调度（每 5 分钟轮询）
- Phase 2c: Docker Compose 新增 `celery_worker` + `celery_beat` 服务
- Phase 2c: 10 个单元测试（`tests/test_cleanup.py`），mock 检测阈值

**本次 Phase 2c 实现（2026-07-06）:**
- 新建 `app/core/cleanup.py` — `cleanup_expired_slots()` 释放逾期座位（超过预约时段结束时间仍未签到），Celery Beat 和懒清理共用
- 新建 `app/tasks/celery_app.py` — Celery 应用实例，broker=Redis
- 新建 `app/tasks/cleanup.py` — 定义 `release_expired_slots` Celery 共享任务
- Celery Beat 调度在 `app/tasks/celery_app.py` 中配置（每 5 分钟）
- `pyproject.toml` 新增 `celery` 依赖（含 timezone 等配置）
- Docker Compose: `celery_worker`（启动 worker）+ `celery_beat`（启动 Beat 调度器）
- `tests/test_cleanup.py` — 10 个测试（正常释放、无逾期、异常回滚、并发安全等），mock 当前时间检测 30 分钟阈值

**已知注意事项:**
- bcrypt 直接使用（passlib 5.x 不兼容）
- pytest 需要 `pytest-asyncio` + `asyncio_mode = "auto"`（已配置）
- Redis 锁测试用 fakeredis，`acquire()` 返回 `result is not None`
- 远程: `gitee` + `github`，推送用 `git push gitee dev && git push github dev`
- 前端: Element Plus chunk 较大（~1MB），后续可配置 manualChunks 优化
- Redis 本地为 5.0.14，生产部署建议 ≥6.0
- PostgreSQL 本地为 zip 包安装（`D:\P_SQL\...`），非服务模式，需手动 `pg_ctl start`
- Celery worker 依赖 Redis 作为 broker，本地开发需先启动 Redis
- Celery Beat 调度在 Docker Compose 中自动启动，本地开发可手动 `celery -A tasks.celery_app beat` 测试

## 数据库初始化

```bash
# 1. 启动 PostgreSQL
$env:PGDATA = "D:\P_SQL\postgresql-16.14-1-windows-x64-binaries\pgsql\data"
D:\P_SQL\postgresql-16.14-1-windows-x64-binaries\pgsql\bin\pg_ctl start

# 2. 创建库和用户（首次）
"D:\P_SQL\...\bin\psql.exe" -U postgres
# CREATE USER library WITH PASSWORD 'library123';
# CREATE DATABASE library OWNER library;

# 3. 迁移 + 种子数据
alembic upgrade head && python scripts/seed.py
```

## 关键文档

- Phase 1 设计: `docs/superpowers/specs/2026-07-06-library-qa-design.md`
- Phase 1 计划: `docs/superpowers/plans/2026-07-06-library-qa-phase1.md`
- Phase 2a 设计: `docs/superpowers/specs/2026-07-06-library-phase2a-design.md`
- Phase 2a 计划: `docs/superpowers/plans/2026-07-06-library-phase2a.md`
- Phase 2b 设计: `docs/superpowers/specs/2026-07-06-library-phase2b-design.md`
- Phase 2b 计划: `docs/superpowers/plans/2026-07-06-library-phase2b.md`
- Phase 2c 设计: `docs/superpowers/specs/2026-07-06-library-phase2c-design.md`
- Phase 2c 计划: `docs/superpowers/plans/2026-07-06-library-phase2c.md`
