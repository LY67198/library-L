# 图书馆智能服务系统

基于 FastAPI + LangGraph + Vue 3 的高校图书馆智能服务系统，集成 AI 智能问答、馆藏检索、座位预约、读者画像等功能。

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
app/
├── app_main.py                    # FastAPI 入口
├── backend/
│   ├── config/                    # 运行时设置
│   ├── router/                    # health / chat / research / books 端点
│   ├── schemas/                   # 请求 & 响应模型
│   └── service/                   # ChatService + WorkflowService
├── research_agents/               # 深度调研工作流（LangGraph）
│   ├── adapters/                  # LLMClient 协议 + RuleBasedLLMClient
│   ├── memory/                    # MemoryStore 接口 + InMemory 实现
│   ├── state.py                   # ResearchState 状态契约
│   ├── graph.py                   # 节点连线 & 条件路由
│   └── nodes.py                   # 节点实现
├── library_agents/                # 图书馆智能问答 Agent（LangGraph）
│   ├── state.py                   # LibraryState
│   ├── graph.py                   # 主图 + retrieval 子图
│   ├── nodes.py                   # intent / retrieval / stub 节点
│   └── retrieval/                 # Retriever Protocol + 实现
└── front/                         # Vue 3 + Vite 前端
    └── src/
```

## 快速启动

```bash
cd deep_research_scaffold
python -m venv .venv
.\.venv\Scripts\Activate.ps1    # Windows
# source .venv/bin/activate     # macOS/Linux

pip install -r requirements.txt

# 启动后端
cd app
uvicorn app_main:app --reload --port 8000

# 健康检查
curl http://127.0.0.1:8000/api/v1/health

# 启动前端
cd ../front
npm install && npm run dev
```

## API 概览

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/api/v1/health` | 健康检查 |
| POST | `/api/v1/chat` | AI 同步问答 |
| POST | `/api/v1/chat/stream` | AI 流式问答（SSE） |
| GET | `/api/v1/books` | 馆藏检索 |
| POST | `/api/v1/research/run` | 深度调研（同步） |
| POST | `/api/v1/research/stream` | 深度调研（SSE） |

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

## 扩展点

| 优先级 | 扩展点 | 文件 | 工作内容 |
|--------|--------|------|----------|
| 1 | LLM | `adapters/llm.py` | 实现 `LLMClient`，替换 `RuleBasedLLMClient` |
| 2 | 检索 | `library_agents/retrieval/` | 接入 BM25 / Cross-Encoder / RRF |
| 3 | 记忆 | `memory/store.py` | 实现 `MemoryStore`，接入 Redis/Postgres/Milvus |
| 4 | 子图 | `library_agents/graph.py` | reservation/profile 子图从 stub 升级 |

## 许可证

MIT
