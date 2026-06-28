# Library Intelligent Service — CLAUDE.md

> 给 Claude / AI 助手的项目上下文。设计已锁定,直接进入实现。

## 1. 项目概述

**图书馆智能服务系统** — 高校图书馆场景的 AI Agent + RAG 全栈项目。基于 FastAPI + LangGraph v1 + 自研四路召回 RAG,支持馆藏检索、AI 问答、座位预约、政策咨询。具备企业级工程能力,定位为简历项目。

详细设计: [`docs/superpowers/specs/2026-06-28-library-intelligent-service-design.md`](docs/superpowers/specs/2026-06-28-library-intelligent-service-design.md)

## 2. 技术栈

| 层 | 选型 |
|----|------|
| 后端 | FastAPI 0.115+ / Python 3.12 |
| Agent | LangGraph v1(直接用 StateGraph + Command,不用 SubAgentMiddleware) |
| LLM | **DeepSeek-V4-Flash**(OpenAI 兼容) |
| Embedding | **Qwen text-embedding-v2**(DashScope OpenAI 兼容) |
| Rerank | **Qwen qwen3-rerank**(DashScope 专用端点) |
| 数据库 | PostgreSQL 15 + asyncpg + SQLAlchemy 2.0 async |
| 缓存/锁 | Redis 7 |
| 异步任务 | Celery 5 |
| 向量库 | ChromaDB 0.5 |
| 关键词检索 | Whoosh + jieba |
| MCP | `langchain-mcp-adapters` + FastMCP(独立进程) |
| 可观测性 | OpenTelemetry SDK + Jaeger |
| 评估 | Ragas |
| 前端 | Vue 3 + Element Plus + Pinia + Vite |
| 部署 | Docker Compose |
| 鉴权 | JWT HS256(双 token:access 1h + refresh 30d) |

## 3. 目录结构

```
library-intelligent-service/
├── backend/                # FastAPI + LangGraph 后端(本次实施重点)
│   ├── app/
│   │   ├── main.py         # FastAPI 入口 + lifespan
│   │   ├── core/           # config / database / security / exceptions / observability
│   │   ├── api/v1/         # 路由(auth / health / books / seats / chat / admin)
│   │   ├── schemas/        # Pydantic 模型
│   │   ├── services/       # 业务编排
│   │   ├── repositories/   # 数据访问
│   │   ├── models/         # SQLAlchemy ORM(全部带 tenant_id)
│   │   ├── agents/         # LangGraph 多 Agent(Plan 03)
│   │   ├── rag/            # RAG 流水线(Plan 02)
│   │   ├── clients/        # DeepSeek / Qwen 客户端
│   │   ├── mcp_server/     # MCP Server 独立进程(Plan 04)
│   │   └── workers/        # Celery 任务
│   ├── tests/unit/         # 纯函数测试
│   ├── tests/integration/  # testcontainers 真实 DB
│   ├── alembic/            # DB 迁移
│   └── scripts/init_db.py  # 迁移 + 种子
├── frontend/               # Vue 3 用户端 + 管理端(Plan 05)
├── deploy/
│   ├── docker-compose.yml
│   ├── docker-compose.dev.yml
│   └── postgres/init.sql
├── docs/
│   ├── superpowers/
│   │   ├── specs/          # 设计文档
│   │   └── plans/          # 实施计划
│   └── PROJECT_HISTORY.md  # 过程日志(尚未创建)
├── .github/workflows/ci.yml
└── README.md
```

## 4. 核心约束(不可违反)

1. **MVP 不含多模态** — LLMClient / EmbeddingClient 接口预留扩展点,实现抛 `NotImplementedError`
2. **多租户架构底子** — 任何业务表必须有 `tenant_id` 列 + 复合索引前缀;repository 方法强制接 `tenant_id` 参数
3. **RAG 全手写** — BM25 / ChromaDB / RRF / Rerank 不依赖 LangChain 封装,直接调底层 API,RRF 函数自己写
4. **LangGraph 用 v1 原生 Command** — 不用 `SubAgentMiddleware`;Worker 节点返回 `Command(goto=, update=)`
5. **MCP Server 强制鉴权** — 所有 Tool 从 MCP Context 提取 `tenant_id` + `user_id`,不接受调用方传入
6. **并发两层防御** — Redis 分布式锁(性能)+ PG `version` 列(正确性),不能只依赖其中一层
7. **DeepSeek + Qwen(国产)** — LLM/Embedding/Rerank 全部国产模型,中文场景友好,符合国产化趋势
8. **JWT 双 token** — access(1h) + refresh(30d),refresh 可撤销
9. **OTel 全量埋点** — FastAPI / SQLAlchemy / Redis / Celery 自动 + 关键节点手动 span
10. **测试覆盖率门槛** — 总体 ≥75%,核心模块(rag/agents/services/security)≥85%

## 5. 常用命令

```bash
# 开发环境启动(Docker Compose)
cd deploy
docker compose up -d
docker compose exec api python scripts/init_db.py   # 初始化 DB + 种子租户

# 本地开发(热重载)
docker compose -f docker-compose.yml -f docker-compose.dev.yml up

# 测试
cd backend
pytest tests/unit -v                 # 纯函数(无需 Docker)
pytest tests/integration -v          # testcontainers(需 Docker)
pytest --cov=app --cov-fail-under=75 # 覆盖率

# 代码质量
ruff check app/
mypy app/

# 数据库迁移
alembic revision --autogenerate -m "description"
alembic upgrade head
alembic downgrade -1

# 清理
docker compose down -v   # 停止 + 删卷(全清)
```

## 6. 当前状态

**阶段**: 设计阶段完成,Plan 01 已写完待执行。

| 阶段 | 内容 | 状态 |
|------|------|------|
| 设计 | 12 节 spec(架构 / 目录 / 数据模型 / 多 Agent / RAG / 并发 / MCP / OTel / API / 测试 / 部署 / ADR) | ✅ 完成 |
| Plan 01 | M1 基础设施(31 任务):bootstrap / 配置 / 异常 / JWT / 全部 6 张表 / Alembic / Auth API / Health / Docker Compose / CI | ✅ 已写,待执行 |
| Plan 02 | M2 业务服务 + RAG 流水线 | ⏳ 未写 |
| Plan 03 | M3 LangGraph 多 Agent + Chat SSE | ⏳ 未写 |
| Plan 04 | M4 MCP Server 5 Tool + OTel 完整实现 | ⏳ 未写 |
| Plan 05 | M5 前端 + Ragas 评估 + E2E | ⏳ 未写 |

**重要参考路径**:
- 设计文档: `docs/superpowers/specs/2026-06-28-library-intelligent-service-design.md`
- Plan 01: `docs/superpowers/plans/2026-06-28-library-service-plan-01-infrastructure.md`

**已锁定决策**(不可重新讨论):
- 6 个意图(`book_inquiry` / `seat_query` / `seat_book` / `appointment_manage` / `policy_qa` / `general_chat`)
- MCP Server 5 Tool(`search_books` / `get_seats` / `book_seat` / `get_policies` / `get_user_appointments`)
- JWT payload:`{sub, tenant_id, roles, iat, exp, jti, type}`
- 错误响应格式:`{error: {code, message, details, trace_id, request_id}}`

**下一步**: 执行 Plan 01(31 任务),完成后写 Plan 02。
