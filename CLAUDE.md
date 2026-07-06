# 图书馆智能服务系统 — 项目进度

## 项目概述

基于 `deep_research_scaffold`（FastAPI + LangGraph 脚手架）的图书馆智能服务系统。Phase 1 聚焦 AI 智能问答 + 馆藏检索，Phase 2a 实现用户认证 + 座位预约闭环。

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
│   └── lock.py              ← Redis 分布式锁 (SeatLock)
├── models/                  ← Phase 2a 新建
│   ├── base.py              ← SQLAlchemy DeclarativeBase
│   ├── user.py              ← User
│   ├── floor.py             ← Floor
│   ├── zone.py              ← Zone
│   ├── seat.py              ← Seat
│   ├── seat_time_slot.py    ← SeatTimeSlot (核心并发表)
│   └── appointment.py       ← Appointment (操作流水)
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
└── test_seat_api.py               ← Phase 2a ✅
```

## 下一步

**后续 Phase:**
1. 实现真实 LLMClient（对话用 MiniMax/DeepSeek，嵌入/重排序用 Qwen）
2. 初始化 ChromaDB 知识库 + PostgreSQL 图书数据
3. Phase 2b：Celery 超时释放 + 座位可视化前端
4. Phase 3：读者画像 + 知识库管理 + MCP Server + 可观测性

## 断点续接 — 2026-07-06（Phase 2a 完成）

**当前状态:** Phase 2a 全部 21 个任务完成，56 tests passed。

**已实现:**
- Auth: POST /api/v1/auth/register, login, refresh, GET /me
- Seats: GET /api/v1/seats, POST /seats/{id}/book, GET /appointments, POST /appointments/{id}/cancel
- Agent: reservation_subgraph（5 节点）替换 reservation_stub，返回引导性回复
- LLM: extract_booking_params, extract_cancel_params, format_reservation_response

**已知注意事项（不变）:**
- bcrypt 直接使用（passlib 5.x 不兼容）
- pytest 需要 `pytest-asyncio` + `asyncio_mode = "auto"`（已配置）
- Redis 锁测试用 fakeredis，`acquire()` 返回 `result is not None`
- 远程: `gitee` + `github`，推送用 `git push gitee dev && git push github dev`

## 关键文档

- Phase 1 设计: `docs/superpowers/specs/2026-07-06-library-qa-design.md`
- Phase 1 计划: `docs/superpowers/plans/2026-07-06-library-qa-phase1.md`
- Phase 2a 设计: `docs/superpowers/specs/2026-07-06-library-phase2a-design.md`
- Phase 2a 计划: `docs/superpowers/plans/2026-07-06-library-phase2a.md`
