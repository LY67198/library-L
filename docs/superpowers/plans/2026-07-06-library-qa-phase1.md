# Phase 1: AI 智能问答 + 馆藏检索 — 实现计划

> **状态:** 已完成（32 tests passed）

**Goal:** 在 deep_research_scaffold 基础上实现图书馆 AI 智能问答系统 Phase 1

**Architecture:** `app/agents/` 新包实现多 Agent 协作，`app/retrieval/` 独立检索引擎。主图做 9 意图分类路由，检索域子图走 understand → retrieve → format 节点链。`Retriever` Protocol 提供 ChromaDB + SQL 两种实现。`RuleBasedLLMClient` 扩展 9 分类方法。

**Tech Stack:** FastAPI, LangGraph, ChromaDB, Pydantic, Vue 3, Docker

---

## Tasks

- [x] Task 1: LibraryState — 扩展的共享状态
- [x] Task 2: ChatConfig — 聊天配置
- [x] Task 3: Retriever Protocol + StubRetriever
- [x] Task 4: Chat Schemas — 请求/响应 Pydantic 模型
- [x] Task 5: Extend RuleBasedLLMClient — 9 分类 + 新方法
- [x] Task 6: ChromaDBRetriever + SQLBookLookup
- [x] Task 7: Library Nodes — 意图分类 + 检索 + Stub + 直接回答
- [x] Task 8: Library Graph — 主图 + retrieval 子图
- [x] Task 9: ChatService — 组装 + SSE 桥接
- [x] Task 10: Chat Router + Book Router
- [x] Task 11: Register Routers in main.py
- [x] Task 12: Integration Tests — Graph Routing（14 tests）
- [x] Task 13: E2E Tests — Chat API（6 tests）
- [x] Task 14: Frontend — Chat Interface
- [x] Task 15: Docker Setup
- [x] Task 16: Update Requirements
- [x] Task 17: Final Integration Verification（32 tests passed）
- [x] Task 18: Push to Remotes

---

## 后续 Phase 规划

### Phase 2 — 用户系统 + 预约管理

| # | 内容 | 涉及目录 |
|---|------|----------|
| 2.1 | **Alembic 数据库迁移** — `alembic init migrations`，建迁移目录 | 根目录 `migrations/` |
| 2.2 | Auth 模块（注册/登录/JWT） | `app/backend/router/auth_router.py`, `app/core/security.py` |
| 2.3 | User + Appointment SQLAlchemy 模型 | `app/models/` |
| 2.4 | 座位预约/取消/查询 API | `app/backend/router/seat_router.py` |
| 2.5 | Redis 分布式锁并发控制 | `app/core/lock.py` |
| 2.6 | Celery 超时释放 + 提醒任务 | `app/tasks/` |
| 2.7 | `seat_agent` 从 stub 升级 | `app/agents/`（扩展 nodes.py + graph.py） |
| 2.8 | 座位可视化前端页面 | `front/src/views/` |

### Phase 3 — 读者画像 + 知识库管理 + MCP + 可观测性

| # | 内容 | 涉及目录 |
|---|------|----------|
| 3.1 | Profile 模型 + 统计/标签/推荐 API | `app/models/`, `app/agents/` |
| 3.2 | 知识库管理 CRUD（管理员） | `app/backend/router/admin_router.py` |
| 3.3 | MCP Server（5 个 Tool） | `app/mcp_server/` |
| 3.4 | Ragas 评估流水线 | `app/evaluation/` |
| 3.5 | OpenTelemetry + Jaeger 集成 | `app/observability/` |
| 3.6 | 完整 9 页面前端 | `front/src/views/` |
| 3.7 | 数据初始化脚本 | `app/retrieval/ingestion.py` |
