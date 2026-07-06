# Phase 1: AI 智能问答 + 馆藏检索 — 设计文档

## 概述

基于 `deep_research_scaffold` 的 LangGraph 多 Agent 编排能力，构建高校图书馆智能问答系统。Phase 1 聚焦检索域（图书检索、图书推荐、政策咨询），其余意图用 stub 占位，验证架构正确性。

## 技术决策摘要

| 模块 | 决策 |
|------|------|
| Agent 编排 | LangGraph 显式编排，3 个子图（检索域完整实现，预约域/画像域 stub） |
| LLM | `RuleBasedLLMClient` 扩展 9 分类，待替换真实 LLM |
| 检索 | `Retriever` Protocol 插件化 — `ChromaDBRetriever`（政策文档）+ `SQLBookLookup`（图书） |
| State | 在 `ResearchState` 基础上增量扩展，不改原字段 |
| API | 4 端点：health + chat + chat/stream + books |
| 前端 | 脚手架 Vue 前端扩展对话界面 |
| 错误处理 | 四级分级降级 + trace_id 兜底 |
| 测试 | 金字塔分层 + 边界覆盖 + 明确不测清单 |
| 文件结构 | `library_agents/` 新包，与 `research_agents/` 同级并行 |

## 9 种用户意图

| Intent | 说明 | Phase 1 状态 |
|--------|------|-------------|
| `search_book` | 检索图书 | 完整实现 |
| `recommend_book` | 推荐图书 | 完整实现 |
| `policy_query` | 政策咨询（开馆时间/借阅规则等） | 完整实现 |
| `book_seat` | 预约座位 | stub |
| `query_appointment` | 查询预约记录 | stub |
| `cancel_appointment` | 取消预约 | stub |
| `profile_query` | 读者画像/借阅记录 | stub |
| `greeting` | 问候闲聊 | 简单回复 |
| `other` | 未分类兜底 | 简单回复 |

## LangGraph 架构

### 主图

```
START
  → intent_classifier  (9 分类)
    → retrieval_subgraph   (search_book / recommend_book / policy_query)
    → reservation_subgraph (book_seat / query_appointment / cancel_appointment) — stub
    → profile_subgraph     (profile_query) — stub
    → direct_answer        (greeting / other)
  → END
```

路由逻辑：`_route_after_intent(state)` 根据 `intent` 字段决定进入哪个子图。子图返回后直接到 END。

### retrieval_subgraph（唯一完整实现）

```
START
  → understand_query  (提取搜索条件，判断检索类型)
    → policy_retrieval  (ChromaDB 向量检索)
    → book_lookup       (PostgreSQL 字段查询)
    → recommend_retrieve (混合策略)
  → format_response     (结果格式化 + 来源标注)
  → END
```

子图内部路由：`_route_after_understand(state)` 根据 `intent` 和 `context` 选检索分支。

## State 设计

在 `ResearchState` 基础上追加以下字段（原 20 个字段不变）：

```python
# === Phase 1 新增：对话与检索 ===
chat_history: list[dict]       # 对话历史（前端传入）
user_id: str | None            # 用户标识
context: dict                  # 查询条件提取结果
retrieved_docs: list[dict]     # 检索原始结果
reranked_docs: list[dict]      # 重排结果（后续启用）
response: str                  # 最终回复
needs_clarification: bool      # 是否需要追问
clarification_question: str    # 追问内容
subgraph: str                  # 目标子图：retrieval/reservation/profile/direct
subgraph_state: dict           # 子图内部状态（嵌套）
error: str | None              # 错误码
fallback_response: str | None  # 降级回复
```

## Retriever Protocol

```python
from typing import Protocol, runtime_checkable

@runtime_checkable
class Retriever(Protocol):
    """检索器协议 — 和 LLMClient 同级别的扩展点"""
    def search(self, query: str, top_k: int = 5, **kwargs) -> list[dict]:
        """返回 [{"content": "...", "metadata": {...}, "score": 0.95}, ...]"""
        ...

class ChromaDBRetriever:
    """政策文档向量检索"""
    def __init__(self, collection_name: str, persist_dir: str):
        ...
    def search(self, query: str, top_k: int = 5, **kwargs) -> list[dict]:
        ...

class SQLBookLookup:
    """图书字段精确查询 — PostgreSQL"""
    def __init__(self, db_session):
        ...
    def search(self, query: str, top_k: int = 10, **kwargs) -> list[dict]:
        ...
```

后续扩展：`BM25Retriever`、`EnsembleRetriever`（RRF 融合）、`RerankedRetriever`（Cross-Encoder 包装）。

## API 设计

| 方法 | 路径 | 说明 | 状态 |
|------|------|------|------|
| GET | `/api/v1/health` | 健康检查 | 保留 |
| POST | `/api/v1/research/run` | 深度调研（同步） | 保留 |
| POST | `/api/v1/research/stream` | 深度调研（SSE） | 保留 |
| POST | `/api/v1/chat` | 同步问答 | 新增 |
| POST | `/api/v1/chat/stream` | SSE 流式问答 | 新增 |
| GET | `/api/v1/books` | 图书搜索 | 新增 |

### Chat 请求/响应

```python
# POST /api/v1/chat
# Request
class ChatRequest(BaseModel):
    query: str
    user_id: str | None = None
    history: list[dict] | None = None  # [{"role": "user", "content": "..."}, ...]

# Response 200
class ChatResponse(BaseModel):
    intent: str
    response: str
    sources: list[dict]
    subgraph: str

# SSE events: intent → token* → done
# event: intent  → {"intent": "search_book"}
# event: token   → {"content": "《三体》在..."}
# event: done    → {"intent": "...", "response": "...", "sources": [...]}
```

## 错误处理

四级分层降级：

| 层级 | 场景 | 降级行为 |
|------|------|---------|
| L1 意图识别 | LLM 超时/非法值 | 关键词匹配兜底 → `other` |
| L2 检索 | ChromaDB/PostgreSQL 不可用 | 空结果 + 友善提示 |
| L3 回复生成 | LLM 返回空/截断 | 模板拼接检索结果 |
| L4 未知异常 | 未预料的错误 | 全局 ExceptionHandler → `{"error": "...", "trace_id": "..."}` |

节点模式：每个节点 `try/except` 返回 `error` 字段，条件边检测后短路到安全退出节点。SSE 流中通过 `event: error` 通知前端降级。

## 测试策略

| 层级 | 数量 | 测什么 | 依赖 |
|------|------|--------|------|
| E2E | 3-5 | 完整对话 + SSE 流式 | TestClient + 内存 ChromaDB + SQLite |
| 集成 | 10-15 | Graph 路由 + 子图切换 + 错误降级 | `RuleBasedLLMClient` + Stub Retriever |
| 单元 | 20+ | 节点纯函数、Protocol 实现、9 分类规则 | 全部 mock |

明确不测：真实 LLM 输出内容、ChromaDB 向量精度、Vue 组件渲染。

## 项目结构

```
app/
├── app_main.py                    # ← 注册 chat_router + book_router
├── backend/
│   ├── router/
│   │   ├── health_router.py       # 不变
│   │   ├── research_router.py     # 不变
│   │   ├── chat_router.py         # 新增
│   │   └── book_router.py         # 新增
│   ├── schemas/
│   │   └── chat.py                # 新增
│   └── service/
│       ├── workflow_service.py    # 不变
│       └── chat_service.py        # 新增
├── research_agents/               # 完全不变（除 llm.py 扩展方法）
│   └── adapters/
│       └── llm.py                 # 扩展：新增 9 分类 + 回复模板方法
└── library_agents/                # 全新包
    ├── state.py                   # LibraryState（扩展 ResearchState）
    ├── graph.py                   # 主图 + retrieval_subgraph
    ├── nodes.py                   # 节点实现
    ├── config.py                  # ChatConfig
    └── retrieval/
        ├── protocol.py            # Retriever Protocol
        ├── chroma_retriever.py    # ChromaDBRetriever
        └── sql_book_lookup.py     # SQLBookLookup
```

## 扩展路径

Phase 1 架构为后续 Phase 预留了明确的插入点：

- **Phase 2（座位预约）**: `reservation_subgraph` 从 stub 升级为完整子图，加入 Redis 分布式锁
- **Phase 3（用户体系）**: 接入 JWT 认证，`profile_subgraph` 升级
- **Phase 4（知识库管理）**: 图书/文档 CRUD，`SQLBookLookup` 替换为 `EnsembleRetriever`
- **Phase 5（可观测性）**: OpenTelemetry middleware 注入 trace_id
- **LLM 替换**: 实现 `OpenAILLMClient(QwenLLMClient)`，注入 `NodeContext`，graph/nodes 一行不改
