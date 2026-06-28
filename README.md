# Library Intelligent Service / 图书馆智能服务系统

> 面向高校图书馆场景的 AI Agent + RAG 全栈应用,支持馆藏检索、座位预约、政策咨询与通用对话。

## 📍 当前进度

**Plan 01 — 基础设施** ✅ 已完成(31 任务):FastAPI 骨架、PostgreSQL schema、JWT 鉴权、Docker Compose、CI 流水线。
**Plan 02 — 业务服务 + RAG 流水线**:待执行
**Plan 03 — LangGraph 多 Agent + Chat SSE**:待执行
**Plan 04 — MCP Server + 可观测性**:待执行
**Plan 05 — 前端 + Ragas 评估 + E2E**:待执行

设计 spec: [`docs/superpowers/specs/`](docs/superpowers/specs/) (本地保留,不推送)


## ✨ 核心能力

- 📚 **馆藏检索** — 自然语言查询图书(题名 / 作者 / ISBN / 主题)
- 🪑 **座位预约** — 实时查询空闲座位、预约 / 取消
- 📋 **政策咨询** — 借阅规则、开放时间、违章处理
- 💬 **通用对话** — 闲聊兜底与意图分发

## 🛠 技术栈

| 层 | 选型 |
|----|------|
| 后端 | FastAPI · LangGraph v1 (StateGraph + Command) |
| LLM | DeepSeek (OpenAI 兼容) |
| Embedding / Rerank | Qwen / DashScope |
| 数据库 | PostgreSQL 15 + SQLAlchemy 2.0 async + asyncpg |
| 缓存 / 分布式锁 | Redis 7 |
| 异步任务 | Celery 5 |
| 向量库 | ChromaDB |
| 关键词检索 | Whoosh + jieba |
| MCP | FastMCP (独立进程) + langchain-mcp-adapters |
| 可观测性 | OpenTelemetry SDK + Jaeger (OTLP/gRPC) |
| 评估 | Ragas |
| 前端 | Vue 3 · Element Plus · Pinia · Vite |
| 鉴权 | JWT HS256 (双 token: access 1h + refresh 30d) |
| 部署 | Docker Compose |

## 🚀 快速开始

### 环境要求

- Python ≥ 3.12
- Node.js ≥ 18(前端)
- [uv](https://github.com/astral-sh/uv)(Python 包管理)

### 后端

```bash
# 安装依赖
uv sync

# 启动开发服务器
cd app
uvicorn app_main:app --reload --port 8000
```

健康检查:

```bash
curl http://127.0.0.1:8000/api/v1/health
```

### 前端

```bash
cd front
npm install
npm run dev
```

Vite 开发服务器默认代理 `/api` 到 `http://127.0.0.1:8000`。

## ⚙️ 配置

```bash
cp .env.example .env
cp config.example.json config.json
```

需要的环境变量(写入 `.env`):

| 变量 | 说明 |
|------|------|
| `APP_ENV` | `development` / `production` |
| `HOST` / `PORT` | 服务监听地址 |
| `CORS_ALLOW_ORIGINS` | 允许的前端源(逗号分隔) |
| `CONFIG_PATH` | 业务配置文件路径 |

## 📁 项目结构

```
.
├── app/                    # FastAPI 后端
│   ├── app_main.py         # 入口
│   ├── backend/            # 路由 / 配置 / schemas / 服务编排
│   └── research_agents/    # LangGraph 工作流 (节点 / 状态 / 工具 / 适配器)
├── front/                  # Vue 3 前端 (用户端 + 管理端)
├── pyproject.toml          # 依赖声明
├── uv.lock                 # 依赖锁 (236 packages)
├── config.example.json     # 业务配置示例
└── .env.example            # 环境变量示例
```

## 🏗 架构概览

```
┌──────────┐    SSE     ┌─────────────┐    Command     ┌──────────────────┐
│  Vue 3   │ ◄────────► │   FastAPI   │ ◄────────────► │  LangGraph v1    │
│ Frontend │   HTTP     │   Backend   │                │   Multi-Agent    │
└──────────┘            └──────┬──────┘                └────────┬─────────┘
                               │                               │
                  ┌────────────┼────────────┐                  │
                  ▼            ▼            ▼                  ▼
              PostgreSQL    Redis 7     ChromaDB         MCP Server
              SQLAlchemy   缓存/锁       Whoosh           (5 Tools)
              asyncpg                   jieba
```

## 📦 分支策略

- `main` — 默认分支,稳定版本
- `dev` — 日常开发分支

## 📜 许可证

MIT