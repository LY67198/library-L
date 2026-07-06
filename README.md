# 图书馆智能服务系统

基于 FastAPI + LangGraph + Vue 3 的高校图书馆智能服务系统，集成 AI 智能问答、座位预约、馆藏检索、读者画像等功能。

## 功能特性

- **AI 智能问答** — 多 Agent 协作，意图识别 + RAG 检索 + 自动化操作
- **座位可视化** — 楼层可视化座位网格，Redis 分布式锁防并发
- **馆藏检索** — BM25 + ChromaDB Dense + RRF 融合 + Cross-Encoder 重排
- **预约管理** — 预约/取消/历史查询，Celery 超时自动释放
- **读者画像** — 预约统计、行为标签、个性化推荐
- **知识库管理** — 图书/政策文档的增删改查（管理员）
- **MCP Server** — 开放 5 个 Tool，支持外部 AI 客户端接入
- **全链路追踪** — OpenTelemetry + Jaeger 集成

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

## 架构

```
smart-library-ai-agent/
├── app/                           # FastAPI 后端
│   ├── main.py                    # 应用入口
│   ├── config.py                  # 配置管理
│   ├── api/v1/                    # RESTful API 路由层
│   │   ├── chat_router.py         # AI 问答接口（含 SSE 流式）
│   │   ├── book_router.py         # 馆藏检索接口
│   │   └── research_router.py     # 深度调研接口
│   ├── agents/                    # Agent 层（5 个 Agent，LangGraph 编排）
│   │   ├── chat_agent/            # 智能问答 Agent
│   │   ├── book_agent/            # 馆藏检索 Agent
│   │   ├── seat_agent/            # 座位预约 Agent
│   │   ├── profile_agent/         # 读者画像 Agent
│   │   └── research_agent/        # 深度调研 Agent
│   ├── services/                  # 业务服务层
│   ├── models/                    # SQLAlchemy 实体（ORM 映射）
│   ├── repositories/              # 数据访问层（CRUD 封装）
│   ├── retrieval/                 # RAG 检索引擎（BM25 + Dense + RRF + Rerank）
│   ├── core/                      # 基础设施（数据库连接池、异常处理、中间件）
│   ├── mcp_server/                # MCP 协议开放接口
│   ├── evaluation/                # Ragas 评估（RAG 质量量化）
│   ├── observability/             # OpenTelemetry + Jaeger 全链路追踪
│   └── tasks/                     # Celery 异步任务（预约提醒/超时释放）
├── web-frontend/                  # Vue 3 + Element Plus 前端
│   └── src/
│       ├── views/                 # 9 个页面（首页、问答、检索、座位预约等）
│       ├── api/                   # Axios 请求封装
│       ├── stores/                # Pinia 状态管理
│       └── router/                # Vue Router 路由配置
├── docker-compose.yml             # Docker 编排（FastAPI + PostgreSQL + Redis）
└── requirements.txt               # Python 依赖
```

## 快速开始

### 前置要求

- Python 3.10+
- Node.js 18+
- PostgreSQL 15
- Redis 7

### 1. 启动基础设施

```bash
docker-compose up -d
```

启动 PostgreSQL 15、Redis 7、Jaeger（可选）。

### 2. 后端启动

```bash
pip install -r requirements.txt
cp .env.example .env
# 编辑 .env 填入数据库连接和 LLM API Key
uvicorn app.main:app --reload --port 8000
```

API 文档访问 http://localhost:8000/docs

### 3. 前端启动

```bash
cd web-frontend
npm install
npm run dev
```

访问 http://localhost:5173

### 4. 数据初始化

```bash
python -c "from app.core.database import SessionLocal; from app.retrieval.ingestion import IngestionPipeline; db = SessionLocal(); IngestionPipeline(db).build_all(); db.close()"
```

## API 概览

| 方法 | 路径 | 说明 |
|------|------|------|
| POST | `/api/v1/auth/register` | 用户注册 |
| POST | `/api/v1/auth/login` | 用户登录 |
| GET | `/api/v1/auth/me` | 当前用户信息 |
| GET | `/api/v1/books/` | 馆藏检索 |
| GET | `/api/v1/books/{id}` | 图书详情 |
| GET | `/api/v1/seats/` | 座位列表 |
| GET | `/api/v1/seats/available` | 空闲座位 |
| POST | `/api/v1/seats/book` | 预约座位 |
| GET | `/api/v1/appointments/` | 我的预约 |
| POST | `/api/v1/appointments/{id}/cancel` | 取消预约 |
| POST | `/api/v1/chat/` | AI 问答 |
| GET | `/api/v1/chat/stream` | SSE 流式问答 |
| POST | `/api/v1/research/run` | 深度调研（同步） |
| POST | `/api/v1/research/stream` | 深度调研（SSE） |
| GET | `/api/v1/profile` | 读者画像/借阅记录 |

## AI 智能问答

支持 9 种用户意图，多 Agent 协作：

| 意图 | 说明 |
|------|------|
| `search_book` | 检索图书 |
| `recommend_book` | 推荐图书 |
| `policy_query` | 政策咨询（开馆时间/借阅规则等） |
| `book_seat` | 预约座位 |
| `query_appointment` | 查询预约记录 |
| `cancel_appointment` | 取消预约 |
| `profile_query` | 读者画像/借阅记录 |
| `greeting` | 问候闲聊 |
| `other` | 未分类兜底 |

工作流：意图识别 → 路由分发 → 领域 Agent 处理 → 结果返回。

## 数据持久层

采用 Repository 模式隔离业务逻辑与数据访问：

| 层级 | 目录 | 职责 |
|------|------|------|
| 实体层 | `app/models/` | SQLAlchemy ORM 映射（图书、读者、预约、借阅记录等） |
| 数据访问层 | `app/repositories/` | CRUD 封装，提供统一查询接口 |
| 基础设施 | `app/core/` | 数据库连接池、异常处理、中间件、依赖注入 |

## MCP 开放接口

`app/mcp_server/` — 基于 MCP（Model Context Protocol）协议暴露图书馆服务能力，第三方 AI Agent 可直接通过标准协议调用馆藏检索、座位预约、智能问答等能力。

## RAG 评估

`app/evaluation/` — 基于 Ragas 框架对 RAG 问答质量进行量化评估：

| 指标 | 说明 |
|------|------|
| Faithfulness | 答案对检索内容的忠实度 |
| Answer Relevancy | 答案与问题的相关度 |
| Context Precision | 检索结果的精确率 |
| Context Recall | 检索结果的召回率 |

## 可观测性

`app/observability/` — 基于 OpenTelemetry + Jaeger 实现全链路追踪，覆盖 HTTP 请求 → Agent 节点 → 检索调用 → LLM 调用的完整调用链，支持性能瓶颈定位与异常排查。

## 异步任务

`app/tasks/` — 基于 Celery + Redis Broker 的异步任务队列：

| 任务 | 说明 |
|------|------|
| 预约提醒 | 座位预约到期前发送通知 |
| 超时释放 | 超时未签到自动释放座位 |
| 借阅逾期 | 逾期提醒与罚金计算 |

## 前端页面

`web-frontend/` — Vue 3 + Element Plus + Vite：

| 层级 | 技术 | 说明 |
|------|------|------|
| 视图层 | `src/views/` | 9 个页面：首页、AI 问答、馆藏检索、图书详情、座位预约、预约管理、读者画像、深度调研、管理后台 |
| 接口层 | `src/api/` | Axios 封装，统一请求拦截与错误处理 |
| 状态管理 | `src/stores/` | Pinia，管理用户态、聊天记录、预约状态 |
| 路由 | `src/router/` | Vue Router，含路由守卫与权限校验 |

## 亮点设计

### 并发预约控制

Redis 分布式锁（`SET NX EX`）+ PostgreSQL 乐观锁双重保障，防止座位超卖。

### 混合检索

四路召回：BM25 关键词 + ChromaDB 向量 + RRF 融合 + Cross-Encoder 重排。

### 多 Agent 架构

意图识别 → 路由分发 → 领域 Agent 处理，支持 9 种用户意图。

## 扩展点

| 优先级 | 扩展点 | 目录 | 工作内容 |
|--------|--------|------|----------|
| 1 | LLM | `app/agents/` | 实现 `LLMClient`，替换 `RuleBasedLLMClient` |
| 2 | 检索 | `app/retrieval/` | 接入 BM25 / Cross-Encoder / RRF |
| 3 | 记忆 | `app/core/` | 实现 `MemoryStore`，接入 Redis/Postgres/Milvus |
| 4 | 子图 | `app/agents/seat_agent/` `app/agents/profile_agent/` | 预约/画像子图从 stub 升级 |

## 许可证

MIT
