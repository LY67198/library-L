# 图书馆智能服务系统

基于 FastAPI + LangGraph + Vue 3 的高校图书馆智能服务系统。

**Phase 1 完成** — AI 智能问答 + 馆藏检索，32 tests passed。

## 架构

```text
front/
  Vue 3 + Vite 聊天界面
  - 提交问答请求
  - 消费 SSE 流式事件

app/
  app_main.py              # FastAPI 入口
  agents/                  # Phase 1 新增 — 图书馆 Agent 层
    state.py               # LibraryState 共享状态
    graph.py               # 主图 + retrieval 子图
    nodes.py               # 9 节点 + LibraryNodeContext
    config.py              # ChatConfig
    retrieval/
      protocol.py          # Retriever Protocol + StubRetriever
      chroma_retriever.py  # ChromaDB 向量检索（政策文档）
      sql_book_lookup.py   # PostgreSQL 图书字段查询
  backend/
    config/                # FastAPI 运行时配置
    router/
      health_router.py     # 健康检查
      research_router.py   # 深度调研（保留）
      chat_router.py       # Phase 1 新增 — 同步 + SSE 流式问答
      book_router.py       # Phase 1 新增 — 馆藏检索
    schemas/
      chat.py              # Phase 1 新增 — ChatRequest/Response 模型
    service/
      workflow_service.py  # 深度调研服务（保留）
      chat_service.py      # Phase 1 新增 — Agent 组装 + SSE 桥接
  research_agents/         # 脚手架原有（llm.py 扩展 9 分类）
    adapters/llm.py        # LLMClient Protocol + RuleBasedLLMClient
    ...

tests/                     # 32 tests
  test_intent_classification.py  # 12 个 9 分类测试
  test_library_graph.py          # 14 个图路由测试
  test_chat_api.py               # 6 个 E2E API 测试
```

## AI 智能问答工作流

```text
START
  -> intent_classifier  (9 意图识别)
    -> retrieval_subgraph    (search_book / recommend_book / policy_query)
      -> understand_query
      -> policy_retrieve / book_lookup / recommend_retrieve
      -> format_response
    -> reservation_stub      (book_seat / query_appointment / cancel_appointment)
    -> profile_stub          (profile_query)
    -> direct_answer         (greeting / other)
  -> END
```

默认使用 `RuleBasedLLMClient`（关键词规则引擎）提供确定性输出，无需 API Key 即可运行。替换 `app/research_agents/adapters/llm.py` 接入真实 LLM。

## 9 种用户意图

| 意图 | 说明 | Phase 1 |
|------|------|---------|
| `search_book` | 检索图书 | 完整实现 |
| `recommend_book` | 推荐图书 | 完整实现 |
| `policy_query` | 政策咨询 | 完整实现 |
| `book_seat` | 预约座位 | stub |
| `query_appointment` | 查询预约 | stub |
| `cancel_appointment` | 取消预约 | stub |
| `profile_query` | 读者画像 | stub |
| `greeting` | 问候 | 简单回复 |
| `other` | 兜底 | 简单回复 |

## 快速开始

```powershell
cd deep_research_scaffold

# 安装依赖（使用 uv）
uv sync

# 启动后端
cd app
uv run uvicorn app_main:app --reload --port 8000

# 健康检查
curl http://127.0.0.1:8000/api/v1/health

# 测试问答
curl -X POST http://127.0.0.1:8000/api/v1/chat `
  -H "Content-Type: application/json" `
  -d '{"query":"有没有《三体》"}'

# 启动前端
cd ../front
npm install
npm run dev
```

## API 端点

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/api/v1/health` | 健康检查 |
| POST | `/api/v1/research/run` | 深度调研（同步） |
| POST | `/api/v1/research/stream` | 深度调研（SSE） |
| POST | `/api/v1/chat` | AI 问答（同步） |
| POST | `/api/v1/chat/stream` | AI 问答（SSE 流式） |
| GET | `/api/v1/books` | 馆藏检索 |

## 运行测试

```powershell
uv run pytest tests/ -v
# 32 passed
```

## 扩展点

| 优先级 | 扩展点 | 文件 | 工作内容 |
|--------|--------|------|----------|
| 1 | LLM | `research_agents/adapters/llm.py` | 实现真实 LLMClient，替换 RuleBasedLLMClient |
| 2 | 检索 | `agents/retrieval/` | 接入 ChromaDB / BM25 / Cross-Encoder |
| 3 | 子图 | `agents/nodes.py` | 预约/画像子图从 stub 升级 |
| 4 | 记忆 | `research_agents/memory/store.py` | 接入 Redis/Postgres 持久化 |

## 后续 Phase

- **Phase 2** — 用户系统 + 座位预约 + Redis 分布式锁 + Celery
- **Phase 3** — 读者画像 + 知识库管理 + MCP Server + 可观测性
