# 图书馆智能服务系统 — 设计文档

> 基于 LangGraph 多 Agent + 自研四路召回 RAG 的高校图书馆智能服务系统
> 支持馆藏检索、AI 问答、座位预约、政策咨询
>
> **作者**: 设计阶段
> **日期**: 2026-06-28
> **状态**: 草案,等待评审

---

## 目录

1. [总体架构与技术栈](#1-总体架构与技术栈)
2. [模块结构与目录布局](#2-模块结构与目录布局)
3. [数据模型与 PostgreSQL Schema](#3-数据模型与-postgresql-schema)
4. [多 Agent 工作流(LangGraph v1)](#4-多-agent-工作流langgraph-v1)
5. [RAG 流水线](#5-rag-流水线)
6. [并发控制(Redis 锁 + PG 乐观锁)](#6-并发控制redis-锁--pg-乐观锁)
7. [MCP Server 设计](#7-mcp-server-设计)
8. [可观测性(OpenTelemetry + Jaeger)](#8-可观测性opentelemetry--jaeger)
9. [API 端点 + 错误处理](#9-api-端点--错误处理)
10. [测试策略](#10-测试策略)
11. [部署(Docker Compose)](#11-部署docker-compose)
12. [设计决策记录(ADR 摘要)](#12-设计决策记录adr-摘要)

---

## 0. 项目背景与范围

### 0.1 一句话定位

基于 FastAPI + LangGraph v1 + 多路召回 RAG + MCP 协议的高校图书馆智能服务系统,具备企业级工程落地能力,作为简历项目。

### 0.2 已锁定的关键决策

| 维度 | 决策 | 备注 |
|------|------|------|
| 业务范围 | 馆藏检索 / AI 问答 / 座位预约 / 政策咨询 | 6 个意图见 §4.2 |
| MVP 范围 | P0(多 Agent + 四路召回 + 并发预约) + P1(Celery 超时 + SSE + MCP 5 Tool) | 详见附录 C 里程碑 |
| 部署形态 | 单租户 + 多租户架构底子 | tenant_id 列 + 中间件透传 |
| 与 scaffold 关系 | 复用架构模式 + 重写代码 | 仓库独立 |
| LLM | DeepSeek-V4-Flash | OpenAI 兼容 |
| Embedding | Qwen text-embedding-v2 | DashScope OpenAI 兼容 |
| Rerank | Qwen qwen3-rerank | DashScope 专用端点 |
| 多模态 | 不做,接口预留扩展点 | 2 期路线 |
| 鉴权 | 学号 + 密码 + JWT(HS256,双 token) | 留 OAuth2 接口 |
| 架构风格 | 手写 RAG + LangGraph v1 多 Agent + MCP Server | 参考代码问题多,全部自研 |

---

## 1. 总体架构与技术栈

### 1.1 技术栈定版

| 层 | 选型 | 用途 |
|----|------|------|
| 后端框架 | FastAPI 0.115+ | RESTful + SSE 流式 |
| 工作流 | LangGraph v1 | 多 Agent 编排 + 状态机 |
| Agent 基座 | LangChain v1(直接用 StateGraph + Command,不用 SubAgentMiddleware) | 中等复杂度的 Agent 编排 |
| 向量库 | ChromaDB 0.5 | 文档/政策 Dense Embedding |
| 关键词检索 | Whoosh + jieba | BM25 中文分词 |
| 重排模型 | Qwen qwen3-rerank | Cross-Encoder 重排 |
| LLM | DeepSeek-V4-Flash | 意图/规划/生成 |
| Embedding | Qwen text-embedding-v2 | Dense 向量 |
| 关系库 | PostgreSQL 15 | 业务数据 + JSONB |
| 缓存/锁 | Redis 7 | 分布式锁 + 限流 + Celery broker |
| 异步任务 | Celery 5 | 预约超时释放 / 异步索引 |
| MCP | `langchain-mcp-adapters` + FastMCP | 5 个 Tool 暴露 |
| 可观测性 | OpenTelemetry SDK + Jaeger | 全链路 trace |
| 评估 | Ragas | RAG 质量指标 |
| 前端 | Vue 3 + Element Plus + Pinia + Vite | 管理后台 + 用户端 |
| 部署 | Docker Compose | 单机一键启动 |

### 1.2 系统拓扑图

```
┌─────────────────────────────────────────────────────────────┐
│                       前端 (Vue 3 + Element Plus)              │
│   用户端(检索/预约/AI问答)  │  管理端(馆藏/策略/统计)            │
└──────────────────────┬──────────────────────────────────────┘
                       │ HTTPS + JWT
┌──────────────────────▼──────────────────────────────────────┐
│                    FastAPI 网关层                              │
│  /api/v1/auth  /api/v1/books  /api/v1/seats  /api/v1/chat    │
│  /api/v1/appointments  /api/v1/admin   /api/v1/mcp            │
│                                                               │
│  ┌─────────────┐  ┌──────────────┐  ┌───────────────────┐   │
│  │ Auth MW     │→ │ Tenant MW    │→ │ Trace MW (OTel)   │   │
│  └─────────────┘  └──────────────┘  └───────────────────┘   │
└──────────────────────┬──────────────────────────────────────┘
                       │
       ┌───────────────┼───────────────┐
       ▼               ▼               ▼
┌─────────────┐ ┌──────────────┐ ┌──────────────┐
│ 业务服务层    │ │ Agent 层      │ │ MCP Server   │
│ BookService │ │ LangGraph v1 │ │ 5 Tools      │
│ SeatService │ │ Supervisor + │ │ (stdio/HTTP) │
│ ApptService │ │ Worker Agents│ │              │
│ PolicySvc   │ │ Tools(MCP内) │ │              │
└──────┬──────┘ └──────┬───────┘ └──────┬───────┘
       │              │               │
       ▼              ▼               ▼
   ┌───────┐   ┌──────────────┐  ┌──────────────┐
   │ Repo  │   │ RAG 流水线    │  │ MCP Adapter  │
   │ 层    │   │ BM25+Dense   │  │ (独立进程)   │
   │       │   │ +RRF+Rerank  │  │              │
   └───┬───┘   └──────┬───────┘  └──────┬───────┘
       │              │               │
       ▼              ▼               ▼
┌──────────────┐ ┌──────────────┐ ┌──────────────┐
│ PostgreSQL 15│ │ ChromaDB    │ │ Redis 7      │
│ (主数据)     │ │ (向量)      │ │ (锁/Celery)  │
└──────────────┘ └──────────────┘ └──────────────┘
                       │
                       ▼
              ┌──────────────┐
              │ Celery Worker│
              │ (超时释放)   │
              └──────────────┘
                       │
                       ▼
              ┌──────────────┐
              │ OTel Collector → Jaeger │
              └──────────────────────────┘
```

### 1.3 关键技术决策

1. **LangGraph v1 用 `Command(goto=, update=)` 做 supervisor/worker**,不用 v1 内置 `SubAgentMiddleware`
2. **RAG 全手写**:`WhooshRetriever` + `ChromaDBRetriever` + 自写 `reciprocal_rank_fusion()` + `QwenReranker`
3. **MCP Server 独立进程**:与 FastAPI 同 pod 但不同容器,通过 stdio 通信。所有 Tool 强制带 `tenant_id` + `current_user_id`,从 MCP `Context` 注入
4. **Celery 只做长收尾**:预约超时释放、异步重建索引。不做主链路异步
5. **OTel 全量埋点**:FastAPI middleware + LangGraph node span + Celery task span + HTTPX out

---

## 2. 模块结构与目录布局

### 2.1 顶层 monorepo 结构

```
library-intelligent-service/
├── backend/                # FastAPI + LangGraph 后端
├── frontend/               # Vue 3 + Element Plus 前端
├── deploy/                 # Docker Compose 编排
├── docs/                   # 设计文档 / ADR
├── scripts/                # 初始化脚本 / seed
└── README.md
```

### 2.2 Backend 详细结构

```
backend/
├── app/
│   ├── main.py                          # FastAPI 入口 + lifespan
│   ├── core/                            # 基础设施(无业务)
│   │   ├── config.py                    # Pydantic Settings
│   │   ├── database.py                  # Async SQLAlchemy engine
│   │   ├── redis_client.py              # Redis async pool + 分布式锁
│   │   ├── celery_app.py                # Celery 实例
│   │   ├── observability.py             # OTel Tracer + Meter
│   │   ├── security.py                  # JWT + bcrypt
│   │   ├── exceptions.py                # 业务异常
│   │   ├── retry.py                     # tenacity 重试
│   │   └── middleware/
│   │       ├── tenant.py
│   │       ├── trace.py
│   │       ├── auth.py
│   │       └── rate_limit.py
│   ├── api/v1/                          # 路由层
│   │   ├── auth.py
│   │   ├── books.py
│   │   ├── seats.py
│   │   ├── appointments.py
│   │   ├── chat.py
│   │   ├── admin.py
│   │   └── deps.py
│   ├── schemas/                         # Pydantic 模型
│   ├── services/                        # 业务编排层
│   │   ├── book_service.py
│   │   ├── seat_service.py
│   │   ├── reservation_service.py
│   │   ├── policy_service.py
│   │   └── user_service.py
│   ├── repositories/                     # 数据访问层
│   │   ├── base.py                      # tenant_id mixin
│   │   ├── book_repository.py
│   │   ├── seat_repository.py
│   │   ├── appointment_repository.py
│   │   ├── policy_repository.py
│   │   └── user_repository.py
│   ├── models/                          # SQLAlchemy ORM
│   │   ├── base.py                      # TenantScopedMixin
│   │   ├── tenant.py
│   │   ├── user.py
│   │   ├── book.py
│   │   ├── seat.py
│   │   ├── appointment.py
│   │   └── policy.py
│   ├── agents/                          # LangGraph 多 Agent
│   │   ├── state.py                     # LibraryAgentState
│   │   ├── graph.py                     # build_graph()
│   │   ├── nodes/
│   │   │   ├── intent_router.py
│   │   │   ├── catalog_agent.py
│   │   │   ├── seat_agent.py
│   │   │   ├── appointment_agent.py
│   │   │   ├── policy_agent.py
│   │   │   ├── general_agent.py
│   │   │   └── response_synth.py
│   │   ├── tools/
│   │   │   ├── catalog_tools.py
│   │   │   ├── seat_tools.py
│   │   │   ├── appointment_tools.py
│   │   │   └── policy_tools.py
│   │   └── middleware/
│   │       ├── pii_mask.py
│   │       ├── retry.py
│   │       └── quota.py
│   ├── rag/                             # RAG 流水线
│   │   ├── retriever/
│   │   │   ├── base.py
│   │   │   ├── bm25_retriever.py
│   │   │   ├── dense_retriever.py
│   │   │   └── hybrid_retriever.py
│   │   ├── fusion/rrf.py
│   │   ├── rerank/qwen_reranker.py
│   │   ├── ingestion/
│   │   │   ├── loader.py
│   │   │   ├── chunker.py
│   │   │   └── indexer.py
│   │   └── pipeline.py
│   ├── clients/                         # 外部 API
│   │   ├── llm_client.py                # DeepSeek
│   │   ├── embedding_client.py          # DashScope Embedding
│   │   └── rerank_client.py             # DashScope Rerank
│   ├── mcp_server/                      # MCP Server 独立进程
│   │   ├── main.py
│   │   ├── server.py
│   │   ├── context.py
│   │   ├── db.py
│   │   └── tools/
│   │       ├── search_books.py
│   │       ├── get_seats.py
│   │       ├── book_seat.py
│   │       ├── get_policies.py
│   │       └── get_user_appointments.py
│   └── workers/                         # Celery 任务
│       ├── appointment_timeout.py
│       └── index_rebuild.py
├── tests/
│   ├── conftest.py
│   ├── unit/
│   ├── integration/
│   └── e2e/
├── alembic/
├── pyproject.toml
├── requirements.txt
└── Dockerfile
```

### 2.3 Frontend 详细结构

```
frontend/
├── src/
│   ├── api/                # axios + SSE 客户端
│   ├── stores/             # Pinia
│   ├── router/
│   ├── views/
│   │   ├── user/
│   │   │   ├── Home.vue
│   │   │   ├── Search.vue
│   │   │   ├── SeatMap.vue
│   │   │   ├── Appointments.vue
│   │   │   └── Chat.vue
│   │   └── admin/
│   │       ├── BookManage.vue
│   │       ├── PolicyManage.vue
│   │       ├── Dashboard.vue
│   │       └── Knowledge.vue
│   ├── components/
│   ├── types/
│   ├── App.vue
│   └── main.ts
├── package.json
├── vite.config.ts
└── Dockerfile
```

### 2.4 部署结构

```
deploy/
├── docker-compose.yml
├── docker-compose.dev.yml
├── .env.example
├── jaeger/
│   ├── otel-collector-config.yaml
├── postgres/init.sql
└── nginx/default.conf
```

---

## 3. 数据模型与 PostgreSQL Schema

### 3.1 ER 概览

```
                ┌──────────────┐
                │   tenants    │
                └──────┬───────┘
                       │ 1:N
        ┌──────────────┼──────────────┬──────────────┐
        ▼              ▼              ▼              ▼
   ┌─────────┐   ┌──────────┐   ┌──────────┐   ┌─────────────┐
   │  users  │   │  books   │   │  seats   │   │  policies   │
   └────┬────┘   └──────────┘   └────┬─────┘   └─────────────┘
        │                            │
        │ N                          │ 1
        │                            │
        │                       ┌────▼─────────┐
        │                       │ appointments │
        │                       │  (含 version)│
        └───────────────────────└──────────────┘

   ┌──────────────┐  ┌─────────────────┐  ┌──────────────────┐
   │ chat_sessions│  │ tool_call_logs  │  │ rag_evaluations  │
   └──────────────┘  └─────────────────┘  └──────────────────┘
```

### 3.2 表 DDL(关键表)

#### `tenants`

```sql
CREATE TABLE tenants (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    code            VARCHAR(32) UNIQUE NOT NULL,
    name            VARCHAR(128) NOT NULL,
    status          VARCHAR(16) NOT NULL DEFAULT 'active',
    config          JSONB NOT NULL DEFAULT '{}',
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);
```

#### `users`

```sql
CREATE TYPE user_role AS ENUM ('student', 'faculty', 'librarian', 'admin');

CREATE TABLE users (
    id              BIGSERIAL PRIMARY KEY,
    tenant_id       UUID NOT NULL REFERENCES tenants(id) ON DELETE RESTRICT,
    student_no      VARCHAR(32) NOT NULL,
    password_hash   VARCHAR(255) NOT NULL,
    full_name       VARCHAR(64) NOT NULL,
    email           VARCHAR(128),
    role            user_role NOT NULL DEFAULT 'student',
    status          VARCHAR(16) NOT NULL DEFAULT 'active',
    last_login_at   TIMESTAMPTZ,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (tenant_id, student_no)
);

CREATE INDEX idx_users_tenant_role ON users(tenant_id, role);
```

#### `books`

```sql
CREATE TYPE book_status AS ENUM ('available', 'borrowed', 'reserved', 'lost');

CREATE TABLE books (
    id              BIGSERIAL PRIMARY KEY,
    tenant_id       UUID NOT NULL REFERENCES tenants(id),
    isbn            VARCHAR(20),
    title           VARCHAR(256) NOT NULL,
    author          VARCHAR(256),
    publisher       VARCHAR(128),
    category        VARCHAR(32),
    location        VARCHAR(64),
    status          book_status NOT NULL DEFAULT 'available',
    total_copies    INT NOT NULL DEFAULT 1,
    available_copies INT NOT NULL DEFAULT 1,
    metadata        JSONB NOT NULL DEFAULT '{}',
    indexed_at      TIMESTAMPTZ,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX idx_books_tenant_title ON books(tenant_id, title);
CREATE INDEX idx_books_tenant_author ON books(tenant_id, author);
CREATE INDEX idx_books_tenant_category ON books(tenant_id, category);
CREATE INDEX idx_books_isbn ON books(tenant_id, isbn) WHERE isbn IS NOT NULL;
```

#### `seats`

```sql
CREATE TYPE seat_status AS ENUM ('available', 'occupied', 'maintenance', 'disabled');
CREATE TYPE seat_zone AS ENUM ('silent', 'group', 'individual', 'computer');

CREATE TABLE seats (
    id              BIGSERIAL PRIMARY KEY,
    tenant_id       UUID NOT NULL REFERENCES tenants(id),
    code            VARCHAR(16) NOT NULL,
    floor           VARCHAR(8) NOT NULL,
    zone            seat_zone NOT NULL,
    status          seat_status NOT NULL DEFAULT 'available',
    has_power       BOOLEAN NOT NULL DEFAULT false,
    has_monitor     BOOLEAN NOT NULL DEFAULT false,
    coord_x         INT NOT NULL,
    coord_y         INT NOT NULL,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (tenant_id, code)
);

CREATE INDEX idx_seats_tenant_floor ON seats(tenant_id, floor);
CREATE INDEX idx_seats_tenant_status ON seats(tenant_id, status);
```

#### `appointments`(关键并发表)

```sql
CREATE TYPE appt_status AS ENUM ('pending', 'confirmed', 'active', 'completed', 'cancelled', 'expired');
CREATE TYPE appt_resource AS ENUM ('seat', 'book', 'room');

CREATE TABLE appointments (
    id              BIGSERIAL PRIMARY KEY,
    tenant_id       UUID NOT NULL REFERENCES tenants(id),
    user_id         BIGINT NOT NULL REFERENCES users(id),
    resource_type   appt_resource NOT NULL,
    resource_id     BIGINT NOT NULL,
    seat_id         BIGINT REFERENCES seats(id),
    start_time      TIMESTAMPTZ NOT NULL,
    end_time        TIMESTAMPTZ NOT NULL,
    status          appt_status NOT NULL DEFAULT 'pending',
    version         INT NOT NULL DEFAULT 0,             -- 乐观锁
    confirmed_at    TIMESTAMPTZ,
    cancelled_at    TIMESTAMPTZ,
    cancel_reason   VARCHAR(128),
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    CHECK (end_time > start_time)
);

CREATE INDEX idx_appt_resource_time ON appointments(tenant_id, resource_type, resource_id, start_time, end_time)
    WHERE status IN ('pending', 'confirmed', 'active');
CREATE INDEX idx_appt_user_status ON appointments(tenant_id, user_id, status);
CREATE INDEX idx_appt_status_endtime ON appointments(status, end_time)
    WHERE status IN ('pending', 'confirmed', 'active');
```

#### `policies`

```sql
CREATE TABLE policies (
    id              BIGSERIAL PRIMARY KEY,
    tenant_id       UUID NOT NULL REFERENCES tenants(id),
    title           VARCHAR(256) NOT NULL,
    content         TEXT NOT NULL,
    category        VARCHAR(32),
    effective_from  DATE,
    effective_to    DATE,
    version         INT NOT NULL DEFAULT 1,
    indexed_at      TIMESTAMPTZ,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX idx_policies_tenant_category ON policies(tenant_id, category);
```

#### `chat_sessions` & `chat_messages`

```sql
CREATE TABLE chat_sessions (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id       UUID NOT NULL REFERENCES tenants(id),
    user_id         BIGINT NOT NULL REFERENCES users(id),
    title           VARCHAR(128),
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX idx_chat_sessions_user ON chat_sessions(tenant_id, user_id, updated_at DESC);

CREATE TABLE chat_messages (
    id              BIGSERIAL PRIMARY KEY,
    session_id      UUID NOT NULL REFERENCES chat_sessions(id) ON DELETE CASCADE,
    role            VARCHAR(16) NOT NULL,
    content         TEXT NOT NULL,
    tool_calls      JSONB,
    citations       JSONB,
    latency_ms      INT,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX idx_chat_messages_session ON chat_messages(session_id, created_at);
```

#### `tool_call_logs`

```sql
CREATE TABLE tool_call_logs (
    id              BIGSERIAL PRIMARY KEY,
    tenant_id       UUID NOT NULL REFERENCES tenants(id),
    user_id         BIGINT REFERENCES users(id),
    source          VARCHAR(16) NOT NULL,           -- 'mcp' / 'agent_internal'
    tool_name       VARCHAR(64) NOT NULL,
    arguments       JSONB NOT NULL,
    result          JSONB,
    status          VARCHAR(16) NOT NULL,
    error_message   TEXT,
    latency_ms      INT,
    trace_id        VARCHAR(64),
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX idx_tool_logs_trace ON tool_call_logs(trace_id);
CREATE INDEX idx_tool_logs_tenant_user_time ON tool_call_logs(tenant_id, user_id, created_at DESC);
```

#### `rag_evaluations`

```sql
CREATE TABLE rag_evaluations (
    id              BIGSERIAL PRIMARY KEY,
    tenant_id       UUID NOT NULL REFERENCES tenants(id),
    eval_set        VARCHAR(64) NOT NULL,
    query           TEXT NOT NULL,
    response        TEXT NOT NULL,
    contexts        JSONB NOT NULL,
    faithfulness    FLOAT,
    answer_relevancy FLOAT,
    context_precision FLOAT,
    context_recall  FLOAT,
    notes           TEXT,
    evaluated_at    TIMESTAMPTZ NOT NULL DEFAULT now()
);
```

### 3.3 租户隔离策略

1. **应用层强制过滤** —— 每个 repository 方法必须接 `tenant_id`,WHERE 拼接
2. **复合索引前缀** —— 所有租户相关表索引都以 `tenant_id` 开头
3. **MCP Context 注入** —— MCP tools 的 tenant_id 从 MCP Context 提取,不接受调用方传入
4. **可选 RLS**(后续) —— PostgreSQL Row-Level Security
5. **跨租户审计** —— 任何跨 tenant 数据访问进 `audit_log`

---

## 4. 多 Agent 工作流(LangGraph v1)

### 4.1 设计原则

1. v1 原生 `Command(goto=, update=)` 做动态路由
2. 不用 `SubAgentMiddleware`
3. 6 个领域 Agent + 1 个 Supervisor(足够覆盖)
4. Agent tools 和 MCP Tools 实现解耦,共享 service 层

### 4.2 6 个领域意图

| 意图 | 覆盖场景 | Worker |
|------|---------|--------|
| `book_inquiry` | 查书 / 推荐 / 分类浏览 | catalog_agent |
| `seat_query` | 查座位 / 查空闲 / 查某楼层 | seat_agent |
| `seat_book` | 预约座位 / 改时间 | seat_agent |
| `appointment_manage` | 查我的 / 取消 | appointment_agent |
| `policy_qa` | 借阅规则 / 开放时间 / 罚款 | policy_agent + RAG |
| `general_chat` | 闲聊 / 不明确 | general_agent |
| `clarify` | 信息不全反问 | intent_router 自处理 |

### 4.3 State Schema

```python
class LibraryAgentState(TypedDict):
    messages: Annotated[list[AnyMessage], add_messages]
    user_id: int
    tenant_id: UUID
    intent: IntentType | None
    entities: dict
    needs_clarification: bool
    clarification_question: str | None
    iteration: int
    max_iterations: int
    worker_outputs: dict[str, dict]
    rag_results: list[dict]
    draft_response: str
    final_response: str
    sources: list[dict]
    error: str | None
```

### 4.4 图拓扑

```
                    ┌─────────────┐
                    │   START     │
                    └──────┬──────┘
                           ▼
              ┌────────────────────────┐
              │     intent_router      │
              └────────────┬───────────┘
                           │ Command(goto=worker|clarify|general, update={intent, entities})
            ┌──────────────┼─────────────────┬──────────────┬─────────────┐
            ▼              ▼                 ▼              ▼             ▼
      ┌──────────┐  ┌──────────┐      ┌──────────┐  ┌──────────┐  ┌──────────┐
      │ catalog  │  │   seat   │      │appointment│  │  policy  │  │  general │
      │  agent   │  │  agent   │      │  agent    │  │  agent   │  │  agent   │
      └────┬─────┘  └────┬─────┘      └─────┬─────┘  └────┬─────┘  └────┬─────┘
           │             │                  │             │             │
           └─────────────┴──────────────────┴─────────────┴─────────────┘
                                      │
                                      ▼
                          ┌─────────────────────┐
                          │  response_synth     │
                          └──────────┬──────────┘
                                     │
                                     ▼
                                  [END]
```

### 4.5 关键节点实现模式

**intent_router**:
- 用 LLM `structured output` 拿 JSON
- 信息不全 → `Command(goto="response_synth", update={clarification_question: ...})`
- 正常 → `Command(goto=worker_map[intent], update={intent, entities})`

**catalog_agent**:
- `bind_tools([search_books_tool, get_book_detail_tool, recommend_books_tool])`
- LLM 决定调哪些 tool,执行后汇总

**policy_agent**:
- 调用 RAG pipeline 拿 top-5 chunks
- LLM 基于引文强制回答

**response_synth**:
- 落库 tool_call_logs + chat_messages
- 返回 `Command(goto=END)`

### 4.6 Agent Tools vs MCP Tools

| 维度 | Agent Tools | MCP Tools |
|------|-----------|----------|
| 装饰器 | `@tool`(LangChain) | `@mcp.tool()`(FastMCP) |
| 调用入口 | Graph 内部 LLM 决策 | 外部 MCP 客户端 |
| 异常处理 | 转成 ToolMessage 让 Agent 重试 | 转成 MCP error response |
| Tenant/User | 从 Runtime context | 从 MCP Context 提取 |
| **共享底层** | service 层 + repository 层 | service 层 + repository 层 |

### 4.7 SSE 流式集成

```python
async def stream_response(state, runtime):
    config = {"configurable": {"thread_id": str(state.get("session_id", ""))}}
    async for event in graph.astream(state, config=config, stream_mode="updates"):
        for node_name, node_output in event.items():
            yield {"type": "phase", "node": node_name, "message": NODE_MESSAGES.get(node_name, node_name)}
            if node_output.get("final_response"):
                yield {"type": "final", "final": ..., "sources": ...}
```

### 4.8 错误处理与重试

1. Worker 失败 → `Command(update={"error": "..."}, goto="response_synth")` → 兜底文案
2. LLM 失败 → Middleware `retry.py` 指数退避 3 次
3. Tool 失败 → 内部 try/except,返回 `{"error": "..."}` 让 LLM 决定
4. 澄清循环 → `iteration < max_iterations` 时可重跑,超限强制 general_chat

---

## 5. RAG 流水线

### 5.1 整体流水线

```
                    query
                      │
       ┌──────────────┴──────────────┐
       ▼                             ▼
┌─────────────┐               ┌─────────────┐
│ BM25 检索   │               │ Dense 检索  │
│ Whoosh+jieba│               │ ChromaDB    │
│  top_k=20   │               │ +Qwen Embed │
└──────┬──────┘               └──────┬──────┘
       │                             │
       └──────────────┬──────────────┘
                      ▼
            ┌──────────────────┐
            │  RRF 融合        │  ← k=60, top_k=30
            └────────┬─────────┘
                     │
                     ▼ 30 个候选
            ┌──────────────────┐
            │  Cross-Encoder   │  ← Qwen3-rerank 批处理 10/批
            └────────┬─────────┘
                     │
                     ▼ top_k=5
            ┌──────────────────┐
            │  Tenant 过滤     │
            └────────┬─────────┘
                     │
                     ▼
              [{content, source_id, score}]
```

### 5.2 文档摄入

**Loader**:支持 .pdf (pypdf) / .docx / .txt / .md

**Chunker**(滑动窗口 + 段落感知):
- `chunk_size=500`, `overlap=80`, `min_chunk=100`
- 先按段落分(双换行),再按窗口合并过短段
- 末尾保留 80 字符重叠

**Indexer**:ChromaDB collection 按 tenant 分(命名 `policies_{tenant_id}`),Whoosh 同样按 tenant 字段;embedding 批 32/批。

### 5.3 BM25 检索

- Whoosh + jieba 中文分词
- `BM25F(K1=1.5, B=0.75)`
- 检索字段:content, title
- top_k=20

### 5.4 Dense 检索

- ChromaDB + Qwen text-embedding-v2
- `collection.query(query_embeddings=[vec], n_results=20, where={"tenant_id": ...})`
- cosine 距离转相似度

### 5.5 混合检索(并发)

```python
bm25_hits, dense_hits = await asyncio.gather(
    self.bm25.retrieve(query, tenant_id),
    self.dense.retrieve(query, tenant_id),
    return_exceptions=True,  # 失败容忍
)
```

### 5.6 RRF 融合(自写)

```python
def reciprocal_rank_fusion(hit_lists, k=60):
    """RRF:score(d) = Σ 1/(k+rank_i(d))

    不需要归一化不同检索器分数(BM25 vs cosine 量纲不同),天然融合。
    """
    rrf_scores = defaultdict(float)
    hit_map = {}
    for hits in hit_lists:
        for rank, hit in enumerate(hits, start=1):
            rrf_scores[hit.chunk_id] += 1.0 / (k + rank)
            if hit.chunk_id not in hit_map or len(hit.content) > len(hit_map[hit.chunk_id].content):
                hit_map[hit.chunk_id] = hit
    sorted_ids = sorted(rrf_scores.keys(), key=lambda x: rrf_scores[x], reverse=True)
    return [_make_hit(hit_map[cid], rrf_scores[cid]) for cid in sorted_ids]
```

### 5.7 Rerank(Qwen3-rerank)

- DashScope 专用端点(非 OpenAI 兼容)
- 批处理 10/批
- 重试 3 次,指数退避
- 输出 top_k=5

### 5.8 缓存

- 本地 LRU(maxsize=1000, TTL 5 分钟)
- Redis(`rag:cache:{tenant_id}:{query_hash}`, TTL 10 分钟)

### 5.9 Ragas 评估

- 50 条人工标注 golden set
- 指标:faithfulness, answer_relevancy, context_precision, context_recall
- 结果写入 `rag_evaluations` 表

---

## 6. 并发控制(Redis 锁 + PG 乐观锁)

### 6.1 两层防御模型

| 层 | 防御对象 | 失败后果 |
|----|---------|---------|
| **Redis 分布式锁** | 业务层并发(多 FastAPI worker) | 短暂超卖 |
| **PostgreSQL 乐观锁** | 锁失效、跨进程竞争 | 数据不一致 |

- Redis 锁:性能优化,挡住 99% 竞争
- PG 乐观锁:正确性保证,UPDATE `WHERE version = ?`

### 6.2 Redis 分布式锁

```python
RELEASE_SCRIPT = """
if redis.call('GET', KEYS[1]) == ARGV[1] then
    return redis.call('DEL', KEYS[1])
else
    return 0
end
"""

class DistributedLock:
    async def __aenter__(self):
        ok = await self.redis.set(self.key, self.token, nx=True, px=self.ttl_ms)
        if not ok: raise LockAcquireError(...)
    async def __aexit__(self, ...):
        await self.redis.eval(RELEASE_SCRIPT, 1, self.key, self.token)
```

- `SET NX PX`:原子加锁 + 5s TTL(防死锁)
- `secrets.token_hex(16)`:唯一持有者标识
- Lua 释放:GET + DEL 原子化,只删自己的 token

### 6.3 PostgreSQL 乐观锁

`appointments.version` 列 + `UPDATE ... WHERE version = expected_version`,0 行受影响 = 冲突。

### 6.4 完整预约流程

1. Redis 锁(3 秒 TTL),重试 3 次,指数退避 100/200/400ms
2. PG `SELECT FOR UPDATE` 锁 seat 行
3. 查时间冲突
4. INSERT 新预约
5. 提交 Celery 任务做超时释放

### 6.5 防死锁

批量预约:按 `seat_id` 升序加锁,逆序释放。

### 6.6 Celery 超时释放

- 预约 `end_time + 30 分钟` 宽限期未签到 → 自动 expired
- `SELECT FOR UPDATE SKIP LOCKED` 跳过已被其他 worker 锁的行
- `celery_beat` 每 5 分钟扫描补刀

### 6.7 故障恢复

| 故障 | 后果 | 恢复机制 |
|------|------|---------|
| Redis 宕机 | 锁失效,直达 DB | DB `SELECT FOR UPDATE` 仍一致 |
| Worker 崩溃 | TTL 到期自动释放 | 5 秒 TTL 是上限 |
| Celery 崩溃 | 超时任务丢失 | beat 5 分钟扫描补刀 |
| PG 锁等待超时 | `LockWaitTimeout` | 上游返回 503 + Retry-After |

---

## 7. MCP Server 设计

### 7.1 定位

MCP Server 是独立 Python 进程(Docker Compose 中独立 container),通过 stdio 或 streamable-http 与客户端(MCP Host)通信。MVP 用 stdio。

### 7.2 关键修复(对比参考代码)

| 问题 | 修复 |
|------|------|
| `get_db()` session 提前关闭 | `contextmanager` + `async with` |
| 缺 `book_seat` Tool | 完整实现,带并发锁 |
| 无鉴权 | 从 MCP Context 强制注入 tenant_id + user_id |
| 无 tenant 隔离 | 所有 Tool 强制注入,ChromaDB collection 按 tenant 分 |

### 7.3 MCP Context 提取

```python
@dataclass(frozen=True)
class ToolContext:
    tenant_id: UUID
    user_id: int
    roles: frozenset[str]
    trace_id: str

    def require_self_or_role(self, target_user_id: int, elevated_role: str) -> None:
        if target_user_id != self.user_id and elevated_role not in self.roles:
            raise PermissionError("Cannot access other user's data")

async def extract_context(ctx: Context) -> ToolContext:
    """从 MCP 请求头 X-Tenant-ID / X-User-ID / X-User-Roles / X-Trace-ID 提取。"""
    ...
```

### 7.4 5 个 Tool 设计

#### `search_books`
- 参数:`query`, `category?`, `page`, `page_size`(1-50)
- 返回:`{items: [...], total, page, has_more}`

#### `get_seats`
- 参数:`floor?`, `status?`, `zone?`, `page`, `page_size`(1-200)
- 返回:`{items: [...含坐标], total, has_more}`

#### `book_seat`
- 参数:`seat_id`, `start_time`(ISO8601), `end_time`(ISO8601)
- 校验:`end > start`, 跨度 ≤ 8h
- 调用 `ReservationService.book_seat()`(复用 Redis 锁 + DB 乐观锁)

#### `get_policies`
- 参数:`keyword`, `use_rag`(默认 True)
- `use_rag=True` 走 RAG 流水线,返回完整内容 + relevance_score
- `use_rag=False` 走精确 LIKE 匹配

#### `get_user_appointments`
- 参数:`target_user_id?`, `status?`, `limit`(1-100)
- **强制鉴权**:`require_self_or_role(target, "librarian")`

### 7.5 MCP Middleware

- `AuthContextMiddleware`:校验 X-Tenant-ID/X-User-ID 必须存在
- `TraceSpanMiddleware`:每个 Tool 调用包 OTel span,跨进程传递 traceparent
- `RateLimitMiddleware`:基于 Redis 每用户每分钟 30 次限流

### 7.6 Docker Compose 部署

独立 service `mcp_server`,`command: ["python", "-m", "app.mcp_server.main"]`,不暴露端口(stdio 通信)。

---

## 8. 可观测性(OpenTelemetry + Jaeger)

### 8.1 三类信号

- **Traces**:全链路追踪
- **Metrics**:聚合指标
- **Logs**:结构化日志(关联 trace_id)

### 8.2 OTel SDK 初始化

- Resource:service.name, version, namespace, env
- Tracer:ParentBased(TraceIdRatioBased(0.1)) — 10% 采样
- Meter:PeriodicExportingMetricReader(15s 间隔)
- Auto-instrumentation:FastAPI, SQLAlchemy, Redis, HTTPX, Celery

### 8.3 手动 Span

- LangGraph 节点:`tracer.start_as_current_span("agent.catalog")`
- RAG 阶段:`rag.bm25`, `rag.dense`, `rag.rrf`, `rag.rerank`
- MCP Tool:`mcp.search_books` 等
- Trace 关联:每个 span 加 `tenant.id`, `user.id`, `intent`

### 8.4 关键自定义指标

| 指标名 | 类型 | 标签 |
|--------|------|------|
| `chat_request_total` | Counter | intent, tenant_id |
| `chat_request_latency_ms` | Histogram | intent, node |
| `rag_retrieval_latency_ms` | Histogram | tenant_id |
| `rag_chunks_returned` | Histogram | - |
| `llm_tokens_total` | Counter | model, agent |
| `seat_booking_total` | Counter | result |
| `redis_lock_acquire_total` | Counter | result, key |
| `mcp_tool_call_total` | Counter | tool_name, status |

### 8.5 MCP 跨进程 Trace

- Tool 调用时从请求头提取 `traceparent`,注入 OTel context
- 调用方在请求中传 `X-Trace-ID`,MCP 端关联到当前 span

### 8.6 Jaeger + OTel Collector

Docker Compose 单容器 jaeger + otel-collector-contrib,tail-based sampling(错误/慢请求/10% 概率)。

### 8.7 关键 Trace 视图

1. 完整 Chat 请求(从入口到 SSE 推送)
2. RAG 流水线子图(展示四路召回耗时)
3. 座位预约并发(展示两层锁)
4. MCP 跨进程调用
5. 失败 trace(LLM 503 → fallback)

---

## 9. API 端点 + 错误处理

### 9.1 API 端点总表

| 方法 | 路径 | 鉴权 | 说明 |
|------|------|------|------|
| POST | `/api/v1/auth/register` | 否 | 用户注册 |
| POST | `/api/v1/auth/login` | 否 | 学号+密码 → JWT |
| POST | `/api/v1/auth/refresh` | 是 | 刷新 token |
| GET | `/api/v1/auth/me` | 是 | 当前用户信息 |
| GET | `/api/v1/books` | 是 | 馆藏检索(?use_rag=true) |
| GET | `/api/v1/books/{id}` | 是 | 图书详情 |
| POST | `/api/v1/books` | librarian | 新增 |
| PATCH | `/api/v1/books/{id}` | librarian | 更新 |
| GET | `/api/v1/seats` | 是 | 座位列表 |
| GET | `/api/v1/seats/available` | 是 | 空闲座位 |
| GET | `/api/v1/seats/floor/{floor}` | 是 | 楼层全座位 |
| POST | `/api/v1/seats/book` | 是 | 预约座位 |
| GET | `/api/v1/appointments` | 是 | 我的预约 |
| GET | `/api/v1/appointments/{id}` | 是 | 预约详情 |
| POST | `/api/v1/appointments/{id}/cancel` | 是 | 取消预约 |
| POST | `/api/v1/chat` | 是 | 一次性问答 |
| POST | `/api/v1/chat/stream` | 是 | SSE 流式问答 |
| GET | `/api/v1/chat/sessions` | 是 | 历史会话 |
| GET | `/api/v1/chat/sessions/{id}/messages` | 是 | 会话消息 |
| GET | `/api/v1/admin/policies` | librarian+ | 政策列表 |
| POST | `/api/v1/admin/policies` | librarian+ | 新增政策(自动入 RAG) |
| PATCH | `/api/v1/admin/policies/{id}` | librarian+ | 更新政策 |
| DELETE | `/api/v1/admin/policies/{id}` | admin | 删除政策(同时清索引) |
| POST | `/api/v1/admin/policies/{id}/reindex` | admin | 手动重建索引 |
| GET | `/api/v1/admin/stats` | admin | 运营统计 |
| GET | `/api/v1/admin/evaluations` | admin | Ragas 结果 |
| POST | `/api/v1/admin/evaluations/run` | admin | 触发评估 |
| GET | `/api/v1/health` | 否 | 健康检查 |

### 9.2 JWT 双 Token

- access_token:HS256,TTL 1 小时
- refresh_token:TTL 30 天,可撤销
- Payload:`{sub, tenant_id, roles, iat, exp, jti}`

### 9.3 分页与过滤约定

- `page` + `page_size`(默认从 1 开始,上限 100)
- 过滤参数小写下划线
- 排序 `?sort=-created_at`
- RAG 模式 `?use_rag=true`

### 9.4 异常层次

```
LibraryBaseError (500)
├── ClientError (400)
│   ├── ValidationError (422)
├── Unauthorized (401)
├── Forbidden (403)
├── NotFound (404)
├── Conflict (409)
├── RateLimited (429)
└── UpstreamError (502)
    ├── LLMUnavailable
    ├── RerankUnavailable
    └── ChromaUnavailable
```

### 9.5 统一错误响应格式

```json
{
  "error": {
    "code": "conflict",
    "message": "Seat already booked in this time slot",
    "details": { "seat_id": 123, "time_range": "..." },
    "trace_id": "abc123...",
    "request_id": "..."
  }
}
```

### 9.6 重试 + 熔断 + 限流

| 调用类型 | 重试 | 最大次数 |
|---------|------|---------|
| LLM | 指数退避 | 3 |
| Embedding | 指数退避 | 3 |
| Rerank | 指数退避 | 3 |
| PostgreSQL | 立即+1s+2s | 3 |
| Redis | 否(快速失败) | 0 |
| ChromaDB | 指数退避 | 2 |
| MCP Server | 指数退避 | 2 |

- 熔断器:failure_threshold=5, recovery_timeout=30s
- 限流:`slowapi` + Redis 后端,Chat 接口 20/min,默认 100/min

---

## 10. 测试策略

### 10.1 测试金字塔

- Unit(150+, commit hook 跑):< 10 秒,核心逻辑 90%+
- Integration(25, PR 跑):< 3 分钟,关键路径 80%+
- E2E(5, nightly + main 跑):< 10 分钟,5 个 user journey 100%

### 10.2 关键测试用例

- `test_rrf_basic`:RRF 融合数学正确性
- `test_intent_router_classify`:6 种意图分类 + 实体抽取
- `test_concurrent_seat_booking_only_one_succeeds`:100 并发预约同一座位,只有 1 成功
- `test_optimistic_lock_prevents_double_cancel`:并发取消只有 1 成功
- `test_hybrid_retrieval_returns_reranked_chunks`:RAG 端到端
- `test_complete_book_inquiry_chat_flow`:E2E 完整聊天流程
- `test_full_seat_booking_then_cancel_flow`:E2E 预约 + 取消

### 10.3 覆盖率门槛

- 总体 fail_under=75%
- `rag/`, `agents/`, `services/`, `core/security.py`:85%+
- `repositories/`, `clients/`:75%+
- `api/`, `mcp_server/`:70%+

### 10.4 CI 流水线

GitHub Actions 三阶段:lint → unit → integration → e2e(main 分支)。Postgres + Redis service 容器,testcontainers 隔离。

---

## 11. 部署(Docker Compose)

### 11.1 服务拓扑

```
postgres (15-alpine)        chromadb (0.5)
redis (7-alpine)            jaeger (all-in-one)
api (uvicorn × 2)           otel-collector
celery_worker (× 2)
celery_beat
mcp_server
frontend (nginx)
```

### 11.2 关键环境变量

```
POSTGRES_PASSWORD
DATABASE_URL=postgresql+asyncpg://...
DATABASE_URL_SYNC=postgresql://...         # Celery 用
REDIS_URL
DEEPSEEK_API_KEY / DEEPSEEK_BASE_URL / DEEPSEEK_MODEL=deepseek-v4-flash
DASHSCOPE_API_KEY / DASHSCOPE_BASE_URL / DASHSCOPE_EMBEDDING_MODEL=text-embedding-v2
QWEN_RERANK_ENDPOINT / QWEN_RERANK_MODEL=qwen3-rerank
JWT_SECRET / JWT_ACCESS_TTL_SECONDS=3600 / JWT_REFRESH_TTL_SECONDS=2592000
APP_ENV / LOG_LEVEL / TRACE_SAMPLE_RATIO=0.1
DEFAULT_TENANT_CODE=main_library
```

### 11.3 初始化流程

```bash
# 1. 启动依赖
docker compose up -d postgres redis chromadb jaeger otel-collector

# 2. 跑迁移
docker compose run --rm api alembic upgrade head

# 3. 种子数据(开发)
docker compose run --rm api python scripts/seed_data.py
```

### 11.4 备份策略

每日凌晨全量备份 PostgreSQL(`pg_dump -Fc`)、ChromaDB 目录、Redis RDB,保留 30 天。

---

## 12. 设计决策记录(ADR 摘要)

### ADR-001: 多模态 MVP 不做,接口预留扩展点

**决策**:LLMClient/EmbeddingClient/RAG Retriever 接口预留多模态字段,实现先抛 `NotImplementedError`。

**Why**:MVP 范围控制,6-8 周节奏不变。架构能演,2 期直接接入不重构。

**How to apply**:面试时可讲"专门为多模态扩展设计了 X/Y/Z 抽象,作为下一阶段路线"。

### ADR-002: 单租户 + 多租户架构底子

**决策**:表带 `tenant_id`,中间件透传,业务代码强制过滤。当前部署单租户。

**Why**:既保持 MVP 简单,又预留 SaaS 演进路径。简历可讲"多租户演进路径设计"。

### ADR-003: LangGraph v1 `Command(goto=, update=)` 而非 SubAgentMiddleware

**决策**:用 v1 原生 Command 做动态路由,不用内置 Middleware。

**Why**:SubAgentMiddleware 封装太厚,面试讲不清内部机制。

**How to apply**:每个 Worker 节点返回 `Command(goto=..., update=...)`,静态边少用。

### ADR-004: RAG 全手写而非 LangChain 封装

**决策**:BM25、ChromaDB、RRF、Rerank 全部手写或直接调底层。

**Why**:LangChain v1 没有内置混合检索 + RRF 融合,封装层反而模糊实现细节。

**How to apply**:RRF 函数自己实现 + 公式写在 docstring,Rerank 直接调 DashScope HTTP。

### ADR-005: MCP Server 独立进程且强制 tenant 注入

**决策**:MCP Server 是独立 Docker container,所有 Tool 从 MCP Context 强制注入 tenant_id + user_id。

**Why**:与 FastAPI 主进程解耦,便于多 MCP 实例扩缩容;避免调用方传入越权参数。

**How to apply**:MCP Tool 不接受 tenant_id 作为参数,只从 `extract_context(ctx)` 取。

### ADR-006: DeepSeek + DashScope(Qwen)而非全栈国际模型

**决策**:LLM 用 DeepSeek-V4-Flash,Embedding/Rerank 用 Qwen。

**Why**:中文场景表现更好,成本低,符合国产化趋势。

**How to apply**:所有 Provider 配置集中在 `config.py`,便于未来切换。

### ADR-007: 两层并发控制(Redis + PG 乐观锁)

**决策**:Redis 锁为性能优化,PostgreSQL `version` 列为正确性保证。

**Why**:Redis 全挂时 DB 仍能保证一致性;DB 不被打爆。

**How to apply**:Redis 锁失败 3 次重试后抛 ConflictError,DB 0 行影响等同抛错。

### ADR-008: Celery 只做长收尾,不做主链路异步

**决策**:预约超时释放、异步索引走 Celery,Chat 主链路同步 + SSE。

**Why**:Chat 需要流式响应,SSE 与 Celery 异步任务模型不匹配。

**How to apply**:Celery 不参与 chat 请求路径,只跑后台 housekeeping。

---

## 附录 A:环境要求

- Python 3.12+
- Node.js 20+
- Docker 24+ / Docker Compose v2
- 8GB+ RAM(本地开发)

## 附录 B:成本估算

| 模型 | 单价 | 一次 RAG 查询估算 |
|------|------|-----------------|
| DeepSeek-V4-Flash | ~¥0.0005/1k tokens | ~¥0.002 |
| text-embedding-v2 | ~¥0.0007/1k tokens | ~¥0.001 |
| qwen3-rerank | ~¥0.001/1k tokens | ~¥0.001 |

跑 1 万次 RAG 查询 ≈ ¥40,演示完全够用。

## 附录 C:交付里程碑(预估)

| 阶段 | 内容 | 时间 |
|------|------|------|
| M1 | 基础设施 + 鉴权 + DB schema + Docker Compose | 1 周 |
| M2 | 业务服务(Book/Seat/Reservation) + RAG 流水线 | 2 周 |
| M3 | LangGraph 多 Agent + Chat SSE | 2 周 |
| M4 | MCP Server 5 Tools + 可观测性 | 1 周 |
| M5 | 前端 + Ragas 评估 + E2E 测试 | 1 周 |
| **总计** | | **7 周** |

---

**END OF SPEC**
