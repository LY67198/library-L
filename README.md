# 图书馆智能服务系统

基于 FastAPI + LangGraph + Vue 3 的高校图书馆智能服务系统，集成 AI 智能问答、座位预约、馆藏检索、读者画像等功能。

> **Phase 1 已完成** — AI 智能问答 + 馆藏检索，32 tests passed。
> **Phase 2a 已完成** — 用户认证 + 座位预约闭环，56 tests passed。
> **Phase 2b 已完成** — 座位可视化前端 + 匿名浏览，57 tests passed。
> **Phase 2c 已完成** — Celery 超时释放，67 tests passed。
> **Phase 3 已完成** — 知识库管理（图书 + 政策文档）+ 管理员权限，96 tests passed。
> **Phase 3.5 已完成** — 真实 LLMClient 接入（MiniMax + DeepSeek），132 tests passed。
> **Phase 3.6 已完成** — 可观测性（TraceMiddleware + 结构化日志 + OpenTelemetry），127 tests passed。
> **Phase 4 已完成** — 读者画像（profile_query + profile_subgraph + BorrowRecord 模型），131 tests passed。

## 功能特性

- **AI 智能问答** — 多 Agent 协作，意图识别 + RAG 检索 + 自动化操作 ✅ Phase 1
- **真实 LLM** — MiniMax 主力 + DeepSeek 兜底，5 个图书馆核心方法已接入 ✅ Phase 3.5
- **馆藏检索** — BM25 + ChromaDB Dense + RRF 融合 + Cross-Encoder 重排 ✅ Phase 1（检索框架就绪）
- **座位可视化** — 楼层区域筛选 + 时段选择 + 座位网格色码 + 一键预约 ✅ Phase 2b
- **预约管理** — 预约/取消/历史查询 ✅ Phase 2a（REST API）
- **超时释放** — Celery Beat 每 5 分钟轮询，自动释放逾期座位 ✅ Phase 2c
- **读者画像** — 预约统计、行为标签、个性化推荐 ✅ Phase 4
- **知识库管理** — 图书/政策文档的增删改查（管理员），ChromaDB 向量检索 ✅ Phase 3
- **MCP Server** — 5 个 Tool (馆藏检索/座位浏览/预约/查约/取消) 通过 SSE + HTTP 暴露 ✅ Phase 4
- **全链路追踪** — Trace ID 注入 + 结构化日志 + OpenTelemetry 自动插桩 + 可选 Jaeger ✅ Phase 3.6

## 技术栈

| 层级 | 技术 | 用途 |
|------|------|------|
| 后端框架 | FastAPI | RESTful API + SSE 流式 |
| Agent 编排 | LangGraph | 多 Agent 工作流引擎 |
| 数据库 | PostgreSQL 15 | 主业务数据 |
| 缓存/锁 | Redis 7 | 分布式锁 + Celery Broker |
| 向量数据库 | ChromaDB | RAG 文档嵌入与检索 |
| 检索引擎 | BM25 + Dense + RRF + Rerank | 四路召回精排 |
| 异步任务 | Celery | 预约提醒/超时释放 |
| 可观测性 | OpenTelemetry + Jaeger | 全链路追踪 |
| 评估 | Ragas | RAG 质量量化指标 |
| 前端 | Vue 3 + Element Plus | 管理后台 + 用户交互 |
| 构建工具 | Vite | 前端工程化 |
| 依赖管理 | uv | Python 包管理 |

## LLM / 模型

| 厂商 | 用途 | 模型 |
|------|------|------|
| MiniMax | 对话 | `MiniMax-M3` |
| Qwen (DashScope) | 嵌入 | `text-embedding-v2` (1024d) |
| Qwen (DashScope) | 重排序 | `qwen3-rerank` |

当前已接入真实 LLM（MiniMax + DeepSeek 双通道兜底），无 API Key 时自动回退 `RuleBasedLLMClient`。配置模板见 `.env.example`。

## 架构（当前）

```
app/
├── agents/                   # 图书馆 Agent 层（graph + nodes + llm_client）
├── backend/
│   ├── router/               # chat, book, auth, seat, admin
│   ├── schemas/              # chat, auth, seat
│   └── service/              # chat, auth, seat, profile
├── core/                     # database, security, deps, lock, cleanup
├── mcp_server/               # MCP Server (5 Tools + SSE)
├── models/                   # User, Floor, Zone, Seat, BorrowRecord, etc.
├── observability/            # TraceMiddleware + 结构化日志
├── tasks/                    # Celery worker + beat
└── app_main.py

front/
├── src/
│   ├── api/                  # client, seats, auth
│   ├── composables/          # useAuth
│   ├── router/               # SPA 路由
│   ├── views/                # HomeView, LoginView, SeatDashboard
│   └── components/           # TimeSlotPicker, ZoneChips, SeatCard, SeatGrid, etc.

tests/                        # 173 tests (131 non-DB)
```

## 快速开始

### 前置要求

- Python 3.10+
- Node.js 18+
- PostgreSQL 15+（需要 `asyncpg` 驱动，DATABASE_URL 使用 `postgresql+asyncpg://` 格式）
- Redis 6.0+（5.x 可运行但需配合 `protocol=2` 兼容设置）

### 1. 后端启动

```bash
cd deep_research_scaffold
uv sync
cp .env.example .env
# 编辑 .env 填入 API Key，确认 DATABASE_URL 使用 postgresql+asyncpg:// 格式

# 首次运行：数据库迁移 + 种子数据
alembic upgrade head
python scripts/seed.py

# 启动
cd app
uv run uvicorn app_main:app --reload --port 8000
```

API 文档访问 http://localhost:8000/docs

### 2. 前端启动

```bash
cd front
npm install
npm run dev
```

访问 http://localhost:5173

### 3. 运行测试

```bash
uv run pytest tests/ -v
```

## API 概览

| 方法 | 路径 | 说明 | 状态 |
|------|------|------|------|
| GET | `/api/v1/health` | 健康检查 | ✅ |
| POST | `/api/v1/research/run` | 深度调研（同步） | ✅ 保留 |
| POST | `/api/v1/research/stream` | 深度调研（SSE） | ✅ 保留 |
| POST | `/api/v1/chat` | AI 问答 | ✅ Phase 1 |
| POST | `/api/v1/chat/stream` | SSE 流式问答 | ✅ Phase 1 |
| GET | `/api/v1/books` | 馆藏检索 | ✅ Phase 1 |
| POST | `/api/v1/auth/register` | 用户注册 | ✅ Phase 2a |
| POST | `/api/v1/auth/login` | 用户登录 | ✅ Phase 2a |
| POST | `/api/v1/auth/refresh` | 刷新 Token | ✅ Phase 2a |
| GET | `/api/v1/auth/me` | 当前用户信息 | ✅ Phase 2a |
| GET | `/api/v1/seats` | 座位列表 | ✅ Phase 2a |
| POST | `/api/v1/seats/{id}/bookings` | 预约座位 | ✅ Phase 2a |
| GET | `/api/v1/appointments` | 我的预约 | ✅ Phase 2a |
| DELETE | `/api/v1/appointments/{id}` | 取消预约 | ✅ Phase 2a |
| GET | `/api/v1/admin/books` | 图书管理列表 | ✅ Phase 3 |
| POST | `/api/v1/admin/books` | 新增图书 | ✅ Phase 3 |
| PUT | `/api/v1/admin/books/{id}` | 更新图书 | ✅ Phase 3 |
| DELETE | `/api/v1/admin/books/{id}` | 删除图书 | ✅ Phase 3 |
| POST | `/api/v1/admin/books/import` | 批量导入图书 | ✅ Phase 3 |
| GET | `/api/v1/admin/documents` | 文档列表 | ✅ Phase 3 |
| POST | `/api/v1/admin/documents` | 上传 Markdown 文档 | ✅ Phase 3 |
| DELETE | `/api/v1/admin/documents/{id}` | 删除文档 | ✅ Phase 3 |
| GET | `/api/v1/profile` | 读者画像 | ✅ Phase 4 |
| GET/POST | `/api/v1/mcp` | MCP SSE 端点 | ✅ Phase 4 |

## AI 智能问答

支持 9 种用户意图，多 Agent 协作：

| 意图 | 说明 | 状态 |
|------|------|------|
| `search_book` | 检索图书 | ✅ Phase 1 |
| `recommend_book` | 推荐图书 | ✅ Phase 1 |
| `policy_query` | 政策咨询（开馆时间/借阅规则等） | ✅ Phase 1 |
| `book_seat` | 预约座位 | ✅ Phase 2a |
| `query_appointment` | 查询预约记录 | ✅ Phase 2a |
| `cancel_appointment` | 取消预约 | ✅ Phase 2a |
| `profile_query` | 读者画像/借阅记录 | ✅ Phase 4 |
| `greeting` | 问候闲聊 | ✅ Phase 1 |
| `other` | 未分类兜底 | ✅ Phase 1 |

工作流：意图识别 → 路由分发 → 领域 Agent 处理 → 结果返回。

## 亮点设计

### 多 Agent 架构

意图识别 → 路由分发 → 领域 Agent 处理，9 种用户意图全部实现。retrieval + reservation + profile 三个子图全部就绪。

### 混合检索（框架就绪）

`Retriever` Protocol 插件化 —— `ChromaDBRetriever` + `SQLBookLookup`，后续可挂载 BM25 + RRF + Cross-Encoder。

### 并发预约控制（Phase 2）

Redis 分布式锁（`SET NX EX`）+ PostgreSQL 乐观锁双重保障，防止座位超卖。

## 扩展点

| 优先级 | 扩展点 | 目录 | 工作内容 |
|--------|--------|------|----------|
| 1 | 检索 | `app/agents/retrieval/` | 接入 BM25 / Cross-Encoder / RRF |
| 2 | 记忆 | `app/agents/memory/` | 实现 `MemoryStore`，接入 Redis/Postgres |
| 3 | 推荐 | `app/agents/` | 个性化推荐引擎 |

## 后续 Phase

- **Phase 1** ✅ — AI 智能问答 + 馆藏检索
- **Phase 2a** ✅ — 用户系统 + 座位预约 + Redis 分布式锁 + JWT 认证
- **Phase 2b** ✅ — 座位可视化前端 + 匿名浏览
- **Phase 2c** ✅ — Celery 超时释放
- **Phase 3** ✅ — 知识库管理（图书 + 政策文档）+ 管理员权限
- **Phase 3.5** ✅ — 真实 LLMClient 接入（MiniMax + DeepSeek）
- **Phase 3.6** ✅ — 可观测性（TraceMiddleware + 结构化日志 + OTel）
- **Phase 4** ✅ — 读者画像（profile_query + profile_subgraph + BorrowRecord 模型）

## 许可证

MIT
