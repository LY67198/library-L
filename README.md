# 图书馆智能服务系统

基于 FastAPI + LangGraph + Vue 3 的高校图书馆智能服务系统，集成 AI 智能问答、座位预约、馆藏检索、读者画像等功能。

> **Phase 1 已完成** — AI 智能问答 + 馆藏检索，32 tests passed。
> **Phase 2a 已完成** — 用户认证 + 座位预约闭环，56 tests passed。

## 功能特性

- **AI 智能问答** — 多 Agent 协作，意图识别 + RAG 检索 + 自动化操作 ✅ Phase 1
- **馆藏检索** — BM25 + ChromaDB Dense + RRF 融合 + Cross-Encoder 重排 ✅ Phase 1（检索框架就绪）
- **座位可视化** — 楼层可视化座位网格，Redis 分布式锁防并发 🔜 Phase 2b
- **预约管理** — 预约/取消/历史查询 ✅ Phase 2a（REST API），Celery 超时自动释放 🔜 Phase 2b
- **读者画像** — 预约统计、行为标签、个性化推荐 🔜 Phase 3
- **知识库管理** — 图书/政策文档的增删改查（管理员） 🔜 Phase 3
- **MCP Server** — 开放 5 个 Tool，支持外部 AI 客户端接入 🔜 Phase 3
- **全链路追踪** — OpenTelemetry + Jaeger 集成 🔜 Phase 3

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

当前 Phase 1 使用 `RuleBasedLLMClient`（关键词规则引擎），无需 API Key。配置模板见 `.env.example`。

## 架构（Phase 1 实际）

```
app/
├── agents/                   # Phase 1 新建 — 图书馆 Agent 层
│   ├── state.py              # LibraryState 共享状态
│   ├── graph.py              # 主图 + retrieval 子图
│   ├── nodes.py              # 9 节点 + LibraryNodeContext
│   ├── config.py             # ChatConfig
│   └── retrieval/
│       ├── protocol.py       # Retriever Protocol + StubRetriever
│       ├── chroma_retriever.py
│       └── sql_book_lookup.py
├── backend/
│   ├── config/               # FastAPI 运行时配置
│   ├── router/
│   │   ├── health_router.py
│   │   ├── research_router.py
│   │   ├── chat_router.py    # Phase 1 新增
│   │   └── book_router.py    # Phase 1 新增
│   ├── schemas/
│   │   └── chat.py           # Phase 1 新增
│   └── service/
│       ├── workflow_service.py
│       └── chat_service.py   # Phase 1 新增
├── research_agents/          # 脚手架原有（llm.py 扩展 9 分类）
│   └── adapters/llm.py       # LLMClient Protocol + RuleBasedLLMClient
└── app_main.py               # FastAPI 入口

front/                        # Vue 3 + Vite 前端（聊天界面）

tests/                        # 32 tests
```

## 快速开始

### 前置要求

- Python 3.10+
- Node.js 18+

### 1. 后端启动

```bash
cd deep_research_scaffold
uv sync
cp .env.example .env
# 编辑 .env 填入 API Key
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
| POST | `/api/v1/seats/{id}/book` | 预约座位 | ✅ Phase 2a |
| GET | `/api/v1/appointments` | 我的预约 | ✅ Phase 2a |
| POST | `/api/v1/appointments/{id}/cancel` | 取消预约 | ✅ Phase 2a |
| GET | `/api/v1/profile` | 读者画像 | 🔜 Phase 3 |

## AI 智能问答

支持 9 种用户意图，多 Agent 协作：

| 意图 | 说明 | Phase 1 |
|------|------|---------|
| `search_book` | 检索图书 | 完整实现 |
| `recommend_book` | 推荐图书 | 完整实现 |
| `policy_query` | 政策咨询（开馆时间/借阅规则等） | 完整实现 |
| `book_seat` | 预约座位 | 完整实现 |
| `query_appointment` | 查询预约记录 | 完整实现 |
| `cancel_appointment` | 取消预约 | 完整实现 |
| `profile_query` | 读者画像/借阅记录 | stub |
| `greeting` | 问候闲聊 | 简单回复 |
| `other` | 未分类兜底 | 简单回复 |

工作流：意图识别 → 路由分发 → 领域 Agent 处理 → 结果返回。

## 亮点设计

### 多 Agent 架构

意图识别 → 路由分发 → 领域 Agent 处理，支持 9 种用户意图。检索域完整实现，预约/画像域 stub 占位，横向扩展即可。

### 混合检索（框架就绪）

`Retriever` Protocol 插件化 —— `ChromaDBRetriever` + `SQLBookLookup`，后续可挂载 BM25 + RRF + Cross-Encoder。

### 并发预约控制（Phase 2）

Redis 分布式锁（`SET NX EX`）+ PostgreSQL 乐观锁双重保障，防止座位超卖。

## 扩展点

| 优先级 | 扩展点 | 目录 | 工作内容 |
|--------|--------|------|----------|
| 1 | LLM | `app/research_agents/adapters/llm.py` | 实现 MiniMax LLMClient，替换 `RuleBasedLLMClient` |
| 2 | 检索 | `app/agents/retrieval/` | 接入 BM25 / Cross-Encoder / RRF |
| 3 | 记忆 | `app/research_agents/memory/` | 实现 `MemoryStore`，接入 Redis/Postgres |
| 4 | 子图 | `app/agents/` | 预约/画像子图从 stub 升级 |

## 后续 Phase

- **Phase 2a** — 用户系统 + 座位预约 + Redis 分布式锁 + JWT 认证（进行中）
- **Phase 2b** — Celery 超时释放 + 座位可视化前端
- **Phase 3** — 读者画像 + 知识库管理 + MCP Server + 可观测性 + Ragas 评估

## 许可证

MIT
