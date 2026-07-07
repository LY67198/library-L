# 图书馆智能服务系统 — 项目进度

## 项目概述

基于 `deep_research_scaffold`（FastAPI + LangGraph 脚手架）的图书馆智能服务系统。Phase 1-4 全部完成：AI 智能问答、座位预约、知识库管理、真实 LLM 接入、MCP Server、可观测性、读者画像。

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

**Phase 3 ✅ — 知识库管理 — 已完成:**

- [x] 设计文档 → `docs/superpowers/specs/2026-07-06-library-phase3-kb-design.md`
- [x] 实施计划 → `docs/superpowers/plans/2026-07-06-library-phase3-kb.md`
- [x] Task 1: DB Migration（books + documents 表 + users.is_admin 列）
- [x] Task 2: Book + Document 模型 + User.is_admin
- [x] Task 3: QwenEmbedder（DashScope text-embedding-v2）
- [x] Task 4: ChromaDBRetriever 补全写入/删除
- [x] Task 5: Auth 改造（JWT is_admin claim + require_admin）
- [x] Task 6-7: Book + Document Pydantic Schemas
- [x] Task 8-9: BookService + DocService
- [x] Task 10-11: Admin Book + Doc Routers
- [x] Task 12: 公开 book_router 改造为真实 DB 查询
- [x] Task 13: app_main.py 注册新路由
- [x] Task 14: 种子数据（admin 用户 + 20 本示例图书）
- [x] Task 15-20: 测试（41 new tests — model, service, API, embedder, chroma）
- [x] 96 tests passed（非 DB）+ 前端构建通过

**Phase 3 后续:**
1. ✅ 真实 LLMClient（对话用 MiniMax/DeepSeek，嵌入/重排序用 Qwen）— 2026-07-07 完成
2. ✅ MCP Server — 2026-07-07 完成（含中间件引用修复）
3. ✅ 可观测性 — 2026-07-07 完成（TraceMiddleware + 结构化日志 + OTel）

### 项目完成度总览

**9 种用户意图：9/9 全部实现**

| Intent | 状态 |
|--------|------|
| `search_book` | ✅ Phase 1 |
| `recommend_book` | ✅ Phase 1 |
| `policy_query` | ✅ Phase 1 |
| `book_seat` | ✅ Phase 2a |
| `query_appointment` | ✅ Phase 2a |
| `cancel_appointment` | ✅ Phase 2a |
| `profile_query` | ✅ Phase 4 |
| `greeting` | ✅ Phase 1 |
| `other` | ✅ Phase 1 |

**子图：3/3 全部实现**

| 子图 | 状态 |
|------|------|
| `retrieval_subgraph` | ✅ Phase 1 |
| `reservation_subgraph` | ✅ Phase 2a |
| `profile_subgraph` | ✅ Phase 4 |

**基础设施：全部完成**

- ✅ 用户认证（JWT + bcrypt）
- ✅ 数据库（PostgreSQL + SQLAlchemy async + Alembic）
- ✅ Redis 分布式锁 + Celery 超时释放
- ✅ 知识库管理（图书/文档 CRUD + ChromaDB）
- ✅ 真实 LLM（MiniMax + DeepSeek 双通道兜底）
- ✅ 前端（Vue 3 + Element Plus 座位可视化 + 对话界面）
- ✅ MCP Server（5 个 Tool + SSE transport）
- ✅ 可观测性（Trace ID + 结构化日志 + OpenTelemetry）
- ✅ Docker Compose 部署

**Phase 3 实施计划:** `docs/superpowers/plans/2026-07-06-library-phase3-kb.md`

## 断点续接 — 2026-07-07（真实 LLMClient ✅ 已完成）

**当前状态:** 真实 LLMClient 已接入，MiniMax 主力 + DeepSeek 兜底 + 规则引擎终极兜底，132 tests passed。

### 真实 LLMClient — 已全部完成

- [x] 设计文档 → `docs/superpowers/specs/2026-07-07-real-llm-client-design.md`
- [x] 实施计划 → `docs/superpowers/plans/2026-07-07-real-llm-client.md`
- [x] AppSettings 新增 MiniMax/DeepSeek 6 个配置字段
- [x] `app/agents/llm_client/` — `RealLLMClient` + 5 个 System Prompt + 辅助函数
- [x] 5 个图书馆核心方法替换为真实 LLM 调用（`classify_library_intent`、`extract_booking_params`、`extract_cancel_params`、`format_library_response`、`format_reservation_response`）
- [x] 8 个深度调研方法委托给 `RuleBasedLLMClient`
- [x] `ChatService` 自动检测 API Key，优先使用 `RealLLMClient`，否则回退规则引擎
- [x] 27 个单元测试（`tests/test_real_llm_client.py`）— mock 覆盖完整链路
- [x] 全量 132 tests passed + 前端构建通过

### 调用链

```
用户请求 → RealLLMClient.xxx()
  → MiniMax (OpenAI SDK, Chat Completions)
  → 失败? → DeepSeek (OpenAI SDK)
  → 失败? → RuleBasedLLMClient（关键词/模板兜底）
```

### 新文件

```
app/agents/llm_client/
├── __init__.py          ← 导出 RealLLMClient
└── client.py            ← RealLLMClient + 5 prompts + _call_with_fallback

tests/
└── test_real_llm_client.py  ← 27 tests（mock-based）
```

## 断点续接 — 2026-07-07（MCP Server ✅ 已完成）

**当前状态:** MCP Server 全部完成，14 tests passed，中间件引用已修复。

### MCP Server — 已全部完成

- [x] 设计文档 → `docs/superpowers/specs/2026-07-07-mcp-server-design.md`
- [x] 实施计划 → `docs/superpowers/plans/2026-07-07-mcp-server.md`
- [x] Task 1: mcp SDK 依赖（`pyproject.toml`）
- [x] Task 2: User.api_key 字段 + Alembic 迁移
- [x] Task 3: MCP auth 模块（ContextVar + API Key 中间件）
- [x] Task 4: 5 个 Tool 实现（search_books, list_seats, book_seat, list_appointments, cancel_appointment）
- [x] Task 5: FastMCP Server + SSE transport
- [x] Task 6: FastAPI 挂载（`/api/v1/mcp`）
- [x] Task 7-9: 测试（14 tests — auth, tools, integration）
- [x] 前端构建通过
- [x] 端点验证：GET /sse → 200（SSE 握手成功），POST /messages → 202 Accepted
- [x] **修复 (2026-07-07)**: `app_main.py` 和 `test_mcp_auth.py` 中间件引用从函数式 `mcp_auth_middleware` 更新为纯 ASGI 类 `McpAuthMiddleware`

### 新文件

```
app/mcp_server/
├── __init__.py          ← 包初始化
├── auth.py              ← API Key 认证（纯 ASGI 中间件 McpAuthMiddleware）
├── tools.py             ← 5 个 Tool 实现
└── server.py            ← FastMCP 实例 + SSE 挂载

tests/
├── test_mcp_auth.py     ← 3 tests
├── test_mcp_tools.py    ← 7 tests
└── test_mcp_integration.py ← 4 tests
```

### MCP 协议说明

tools/list 需先完成 MCP initialize 握手（协议要求）：
```bash
# 1. SSE 连接 → 获取 session_id
# 2. POST /messages → initialize 请求
# 3. POST /messages → notifications/initialized
# 4. 现在可以调用 tools/list
```

## 断点续接 — 2026-07-07（可观测性 ✅ 已完成）

**当前状态:** 可观测性全部完成，127 tests passed（non-DB），端点验证通过。

### 可观测性 — 已全部完成

- [x] 设计文档 → `docs/superpowers/specs/2026-07-07-observability-design.md`
- [x] 实施计划 → `docs/superpowers/plans/2026-07-07-observability.md`
- [x] Task 1: 依赖添加（`pyproject.toml`）
- [x] Task 2: AppSettings 新增 5 个配置字段
- [x] Task 3-4: TraceMiddleware（纯 ASGI、UUID7）+ 结构化日志（JSON/text）+ 9 个测试
- [x] Task 5: app_main.py 集成 — TraceMiddleware + 全局异常 handler + OTel 可选
- [x] Task 6: LLM 调用日志关联 trace_id + 耗时追踪
- [x] Task 7: .env.example 新增可观测性配置段
- [x] Task 8: 127 tests passed + 服务启动验证（X-Trace-Id header ✅）

### 新文件

```
app/observability/
├── __init__.py          ← 导出 TraceMiddleware, get_trace_id, setup_logging
├── middleware.py         ← 纯 ASGI 中间件（UUID7 + ContextVar）
└── logging.py           ← TraceIdFilter + JsonFormatter + setup_logging

tests/
└── test_observability.py  ← 13 tests（8 单元 + 5 集成）
```

### 关键行为

- 每个 HTTP 响应自动携带 `X-Trace-Id` header（UUID7 格式）
- 日志格式 `%(asctime)s | %(levelname)s | %(trace_id)s | %(name)s | %(message)s`
- `LOG_FORMAT=json` 切换到 JSON 格式日志
- OTel FastAPI auto-instrumentation 由 `OTEL_ENABLED=true` 控制
- Jaeger exporter 由 `OTEL_EXPORTER_JAEGER_ENABLED=true` 单独控制
- 全局异常 handler 500 响应体包含 trace_id（开发模式包含 detail）
- LLM 调用日志自动关联 trace_id + 耗时（ms）

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
- Phase 3 KB 设计: `docs/superpowers/specs/2026-07-06-library-phase3-kb-design.md`
- Phase 3 KB 计划: `docs/superpowers/plans/2026-07-06-library-phase3-kb.md`
- 真实 LLMClient 设计: `docs/superpowers/specs/2026-07-07-real-llm-client-design.md`
- 真实 LLMClient 计划: `docs/superpowers/plans/2026-07-07-real-llm-client.md`
- Phase 4 profile_query 设计: `docs/superpowers/specs/2026-07-07-profile-query-design.md`
- Phase 4 profile_query 计划: `docs/superpowers/plans/2026-07-07-profile-query.md`
- Phase 4.1 profile API 设计: `docs/superpowers/specs/2026-07-07-profile-api-design.md`

## 断点续接 — 2026-07-07（profile_query Phase 4 ✅ 已完成）

**当前状态:** profile_query + profile_subgraph 已实现，9/9 意图全部完成，3/3 子图全部实现。131 tests passed（non-DB）+ 前端构建通过。

### profile_query — 已全部完成

- [x] 设计文档 → `docs/superpowers/specs/2026-07-07-profile-query-design.md`
- [x] 实施计划 → `docs/superpowers/plans/2026-07-07-profile-query.md`
- [x] Task 1: `app/models/borrow_record.py` — BorrowRecord + BorrowStatus 模型
- [x] Task 2: Alembic 迁移 — `migrations/versions/22c744cbc6c6_add_borrow_records_table.py`
- [x] Task 3: `tests/test_borrow_model.py` — 4 tests
- [x] Task 4: `app/backend/service/profile_service.py` — ProfileService
- [x] Task 5: `tests/test_profile_service.py` — 5 tests
- [x] Task 6: LLM 层 — `extract_profile_params` + `format_profile_response`（RealLLMClient + RuleBasedLLMClient）
- [x] Task 7: `app/agents/nodes.py` + `app/agents/graph.py` — profile_subgraph 三节点 + 主图升级
- [x] Task 8: `app/backend/service/chat_service.py` — ChatService 注入 session_factory
- [x] Task 9: `tests/test_profile_graph.py` — 5 tests（mock asyncio.run）
- [x] Task 10: `scripts/seed.py` — 3 条借阅记录种子数据
- [x] Task 11: 全量 131 tests passed（non-DB）+ 前端构建通过
- [x] Task 12: CLAUDE.md 更新

### 新文件

```
app/models/borrow_record.py
app/backend/service/profile_service.py
tests/test_borrow_model.py
tests/test_profile_service.py
tests/test_profile_graph.py
migrations/versions/22c744cbc6c6_add_borrow_records_table.py
```

### 项目完成度总览

**9/9 意图全部完成，3/3 子图全部实现，基础设施全部就绪。**

## Phase 4.1 ✅ — GET /api/v1/profile REST 端点 (2026-07-07)

**设计文档:** `docs/superpowers/specs/2026-07-07-profile-api-design.md`
**实施计划:** `docs/superpowers/plans/2026-07-07-profile-api.md`

将 ProfileService 现有能力暴露为 HTTP JSON API。4 个集成测试通过。

### API

```
GET /api/v1/profile?type=all|personal_info|borrowing_history
Authorization: Bearer <token>
```

### 文件变更

| 操作 | 文件 |
|------|------|
| 新建 | `app/backend/schemas/profile.py` — UserInfo, BorrowRecordItem, ProfileResponse |
| 新建 | `app/backend/router/profile_router.py` — `GET /api/v1/profile?type=all` |
| 修改 | `app/backend/service/profile_service.py` — 修复 personal_info bug + 3 级 selectinload |
| 修改 | `app/app_main.py` — 注册 profile_router |
| 新建 | `tests/test_profile_api.py` — 4 tests passed |

### 项目完成度总览

**全部 Phase 完成。9/9 意图 + 3/3 子图 + 全部基础设施 + REST API 全覆盖。**
