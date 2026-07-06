# Phase 1: AI 智能问答 + 馆藏检索 — 实现计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 在 deep_research_scaffold 基础上实现图书馆 AI 智能问答系统 Phase 1（检索域完整实现 + 其余 stub）

**Architecture:** `library_agents/` 新包与 `research_agents/` 同级并行。主图做 9 意图分类路由，检索域子图走 understand → retrieve → format 节点链。`Retriever` Protocol 提供 ChromaDB + SQL 两种实现。`RuleBasedLLMClient` 扩展 9 分类方法。

**Tech Stack:** FastAPI, LangGraph, ChromaDB, Pydantic, Vue 3, Docker

---

### Task 1: LibraryState — 扩展的共享状态

**Files:**
- Create: `app/library_agents/__init__.py`
- Create: `app/library_agents/state.py`

- [ ] **Step 1: Write `app/library_agents/__init__.py`**

```python
```

- [ ] **Step 2: Write `app/library_agents/state.py`**

```python
from __future__ import annotations

from typing import Annotated, TypedDict
import operator


class LibraryState(TypedDict):
    """Library chat state — extends ResearchState fields needed for chat."""
    query: str
    user_id: str | None
    chat_history: list[dict]
    intent: str
    subgraph: str
    context: dict
    retrieved_docs: list[dict]
    response: str
    sources: list[dict]
    needs_clarification: bool
    clarification_question: str
    error: str | None
    fallback_response: str | None


def create_initial_library_state(
    query: str,
    user_id: str | None = None,
    chat_history: list[dict] | None = None,
) -> LibraryState:
    return {
        "query": query,
        "user_id": user_id,
        "chat_history": chat_history or [],
        "intent": "",
        "subgraph": "",
        "context": {},
        "retrieved_docs": [],
        "response": "",
        "sources": [],
        "needs_clarification": False,
        "clarification_question": "",
        "error": None,
        "fallback_response": None,
    }
```

- [ ] **Step 3: Commit**

```bash
git add app/library_agents/__init__.py app/library_agents/state.py
git commit -m "feat: add LibraryState with create_initial_library_state"
```

---

### Task 2: ChatConfig — 聊天配置

**Files:**
- Create: `app/library_agents/config.py`

- [ ] **Step 1: Write `app/library_agents/config.py`**

```python
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ChatConfig:
    model: str = "stub"
    retriever_top_k: int = 5
    max_history_turns: int = 10
    chroma_persist_dir: str = "./chroma_data"
    chroma_collection: str = "library_policies"
```

- [ ] **Step 2: Commit**

```bash
git add app/library_agents/config.py
git commit -m "feat: add ChatConfig dataclass"
```

---

### Task 3: Retriever Protocol + StubRetriever

**Files:**
- Create: `app/library_agents/retrieval/__init__.py`
- Create: `app/library_agents/retrieval/protocol.py`

- [ ] **Step 1: Write `app/library_agents/retrieval/__init__.py`**

```python
from .protocol import Retriever, StubRetriever

__all__ = ["Retriever", "StubRetriever"]
```

- [ ] **Step 2: Write `app/library_agents/retrieval/protocol.py`**

```python
from __future__ import annotations

from typing import Protocol, runtime_checkable


@runtime_checkable
class Retriever(Protocol):
    """Search interface — same extension-point pattern as LLMClient."""

    def search(self, query: str, top_k: int = 5, **kwargs) -> list[dict]:
        """Return [{"content": "...", "metadata": {...}, "score": 0.95}, ...]"""
        ...


class StubRetriever:
    """Deterministic stub that returns placeholder results."""

    def search(self, query: str, top_k: int = 5, **kwargs) -> list[dict]:
        return [
            {
                "content": f"Placeholder result {idx} for: {query}",
                "metadata": {"source": f"stub-{idx}"},
                "score": 0.9 - idx * 0.1,
            }
            for idx in range(1, min(top_k, 3) + 1)
        ]
```

- [ ] **Step 3: Commit**

```bash
git add app/library_agents/retrieval/
git commit -m "feat: add Retriever Protocol and StubRetriever"
```

---

### Task 4: Chat Schemas — 请求/响应 Pydantic 模型

**Files:**
- Create: `app/backend/schemas/chat.py`

- [ ] **Step 1: Write `app/backend/schemas/chat.py`**

```python
from __future__ import annotations

from pydantic import BaseModel, Field


class ChatRequest(BaseModel):
    query: str = Field(..., min_length=1, max_length=2000)
    user_id: str | None = None
    history: list[dict] | None = None


class ChatResponse(BaseModel):
    intent: str
    response: str
    sources: list[dict]
    subgraph: str


class BookSearchResult(BaseModel):
    id: str
    title: str
    author: str
    isbn: str | None = None
    location: str | None = None
    available: int = 0
```

- [ ] **Step 2: Commit**

```bash
git add app/backend/schemas/chat.py
git commit -m "feat: add ChatRequest, ChatResponse, BookSearchResult schemas"
```

---

### Task 5: Extend RuleBasedLLMClient — 9 分类 + 新方法

**Files:**
- Modify: `app/research_agents/adapters/llm.py`

- [ ] **Step 1: Write the test for 9 classification**

```bash
mkdir -p tests
```

Create `tests/test_intent_classification.py`:

```python
import pytest
from research_agents.adapters.llm import RuleBasedLLMClient


@pytest.fixture
def llm():
    return RuleBasedLLMClient()


@pytest.mark.parametrize("query,expected", [
    ("有没有《三体》这本书", "search_book"),
    ("帮我找一下Python编程的书", "search_book"),
    ("推荐几本小说看看", "recommend_book"),
    ("想看书但不知道看什么", "recommend_book"),
    ("图书馆几点开门", "policy_query"),
    ("借书能借多久", "policy_query"),
    ("我要预约座位", "book_seat"),
    ("帮我查一下我的预约", "query_appointment"),
    ("取消我的预约", "cancel_appointment"),
    ("我的借阅记录", "profile_query"),
    ("你好", "greeting"),
    ("今天天气怎么样", "other"),
])
def test_classify_library_intent(llm, query, expected):
    result = llm.classify_library_intent(query)
    assert result == expected
```

- [ ] **Step 2: Run test to verify it fails**

```bash
python -m pytest tests/test_intent_classification.py -v
```
Expected: FAIL — `AttributeError: 'RuleBasedLLMClient' object has no attribute 'classify_library_intent'`

- [ ] **Step 3: Extend `LLMClient` Protocol and `RuleBasedLLMClient`**

Edit `app/research_agents/adapters/llm.py` — add to `LLMClient` Protocol:

```python
    def classify_library_intent(self, query: str) -> str: ...

    def format_library_response(self, intent: str, query: str, docs: list[dict]) -> str: ...

    def stub_message(self, intent: str) -> str: ...
```

Add to `RuleBasedLLMClient`:

```python
    def classify_library_intent(self, query: str) -> str:
        lowered = query.lower()
        intent_rules = [
            ("recommend_book", ["推荐", "推荐几本", "不知道看什么", "有什么好书", "推荐一下"]),
            ("search_book", ["有没有", "找一下", "找一本", "查一下", "检索", "搜索", "在哪", "有没有"]),
            ("policy_query", ["几点", "开门", "关门", "借书", "借多久", "罚款", "规则", "规定", "怎么借", "借阅"]),
            ("book_seat", ["预约座位", "占座", "订座", "座位", "选座"]),
            ("cancel_appointment", ["取消预约", "取消", "删除预约"]),
            ("query_appointment", ["我的预约", "预约记录", "预约查询"]),
            ("profile_query", ["借阅记录", "我的记录", "借了哪些", "借过什么", "读者画像"]),
            ("greeting", ["你好", "hi", "hello", "嗨", "早上好", "下午好", "晚上好"]),
        ]
        for intent, markers in intent_rules:
            if any(marker in lowered for marker in markers):
                return intent
        return "other"

    def format_library_response(self, intent: str, query: str, docs: list[dict]) -> str:
        if not docs:
            return f"未找到与「{query}」相关的结果，请尝试其他关键词。"
        lines = [f"为您找到以下结果：", ""]
        for idx, doc in enumerate(docs, 1):
            content = doc.get("content", "")
            meta = doc.get("metadata", {})
            source = meta.get("source", meta.get("title", ""))
            loc = meta.get("location", meta.get("locator", ""))
            line = f"{idx}. {content}"
            if source:
                line += f"  [{source}]"
            if loc:
                line += f" — {loc}"
            lines.append(line)
        return "\n".join(lines)

    def stub_message(self, intent: str) -> str:
        messages = {
            "book_seat": "座位预约功能正在开发中，敬请期待。",
            "query_appointment": "预约查询功能正在开发中，敬请期待。",
            "cancel_appointment": "取消预约功能正在开发中，敬请期待。",
            "profile_query": "读者画像功能正在开发中，敬请期待。",
        }
        return messages.get(intent, "该功能正在开发中，敬请期待。")
```

- [ ] **Step 4: Run test to verify it passes**

```bash
python -m pytest tests/test_intent_classification.py -v
```
Expected: 12 PASS

- [ ] **Step 5: Commit**

```bash
git add app/research_agents/adapters/llm.py tests/test_intent_classification.py
git commit -m "feat: extend LLMClient with 9 library intent classification"
```

---

### Task 6: ChromaDBRetriever + SQLBookLookup

**Files:**
- Create: `app/library_agents/retrieval/chroma_retriever.py`
- Create: `app/library_agents/retrieval/sql_book_lookup.py`

- [ ] **Step 1: Write `chroma_retriever.py`**

```python
from __future__ import annotations


class ChromaDBRetriever:
    """Policy document vector search via ChromaDB."""

    def __init__(self, collection_name: str = "library_policies", persist_dir: str = "./chroma_data"):
        self._collection_name = collection_name
        self._persist_dir = persist_dir
        self._client = None
        self._collection = None

    def _ensure_initialized(self):
        if self._collection is not None:
            return
        try:
            import chromadb
            from chromadb.config import Settings
            self._client = chromadb.PersistentClient(
                path=self._persist_dir,
                settings=Settings(anonymized_telemetry=False),
            )
            self._collection = self._client.get_or_create_collection(
                name=self._collection_name,
            )
        except ImportError:
            raise RuntimeError("chromadb is not installed. Run: pip install chromadb")
        except Exception as exc:
            raise RuntimeError(f"Failed to connect to ChromaDB: {exc}")

    def search(self, query: str, top_k: int = 5, **kwargs) -> list[dict]:
        try:
            self._ensure_initialized()
            assert self._collection is not None
            results = self._collection.query(
                query_texts=[query],
                n_results=top_k,
            )
            docs = []
            if results.get("documents") and results["documents"][0]:
                for idx, doc in enumerate(results["documents"][0]):
                    meta = {}
                    if results.get("metadatas") and results["metadatas"][0]:
                        meta = results["metadatas"][0][idx] or {}
                    score = 1.0
                    if results.get("distances") and results["distances"][0]:
                        dist = results["distances"][0][idx]
                        score = 1.0 / (1.0 + dist) if dist is not None else 1.0
                    docs.append({"content": doc, "metadata": meta, "score": score})
            return docs
        except RuntimeError:
            raise
        except Exception as exc:
            raise RuntimeError(f"ChromaDB search failed: {exc}")
```

- [ ] **Step 2: Write `sql_book_lookup.py`**

```python
from __future__ import annotations

from typing import Any


class SQLBookLookup:
    """Book field search via PostgreSQL LIKE queries."""

    def __init__(self, db_url: str = ""):
        self._db_url = db_url
        self._engine: Any = None

    def _ensure_initialized(self):
        if self._engine is not None:
            return
        if not self._db_url:
            raise RuntimeError("Database URL is not configured")
        try:
            from sqlalchemy import create_engine, text
            self._engine = create_engine(self._db_url)
            # verify connection
            with self._engine.connect() as conn:
                conn.execute(text("SELECT 1"))
        except ImportError:
            raise RuntimeError("sqlalchemy is not installed. Run: pip install sqlalchemy")
        except Exception as exc:
            raise RuntimeError(f"Failed to connect to database: {exc}")

    def search(self, query: str, top_k: int = 10, **kwargs) -> list[dict]:
        """Search books by title, author, or ISBN via SQL LIKE."""
        if not self._db_url:
            return self._stub_results(query, top_k)
        try:
            self._ensure_initialized()
            from sqlalchemy import text
            pattern = f"%{query}%"
            with self._engine.connect() as conn:
                result = conn.execute(
                    text(
                        "SELECT id, title, author, isbn, location, available "
                        "FROM books "
                        "WHERE title LIKE :p OR author LIKE :p OR isbn LIKE :p "
                        "LIMIT :limit"
                    ),
                    {"p": pattern, "limit": top_k},
                )
                rows = result.fetchall()
                return [
                    {
                        "content": f"《{row[1]}》 — {row[2]}",
                        "metadata": {
                            "id": str(row[0]),
                            "title": row[1],
                            "author": row[2],
                            "isbn": row[3],
                            "location": row[4],
                            "available": row[5],
                            "source": "books_db",
                        },
                        "score": 0.95,
                    }
                    for row in rows
                ]
        except RuntimeError:
            raise
        except Exception:
            return self._stub_results(query, top_k)

    def _stub_results(self, query: str, top_k: int) -> list[dict]:
        return [
            {
                "content": f"Placeholder book result for: {query}",
                "metadata": {"source": "stub", "title": query},
                "score": 0.5,
            }
            for _ in range(min(top_k, 3))
        ]
```

- [ ] **Step 3: Update `app/library_agents/retrieval/__init__.py`**

```python
from .protocol import Retriever, StubRetriever
from .chroma_retriever import ChromaDBRetriever
from .sql_book_lookup import SQLBookLookup

__all__ = ["Retriever", "StubRetriever", "ChromaDBRetriever", "SQLBookLookup"]
```

- [ ] **Step 4: Commit**

```bash
git add app/library_agents/retrieval/
git commit -m "feat: add ChromaDBRetriever and SQLBookLookup"
```

---

### Task 7: Library Nodes — 意图分类 + 检索 + Stub + 直接回答

**Files:**
- Create: `app/library_agents/nodes.py`

- [ ] **Step 1: Write `app/library_agents/nodes.py`**

```python
from __future__ import annotations

from dataclasses import dataclass

from research_agents.adapters.llm import LLMClient
from .config import ChatConfig
from .retrieval.protocol import Retriever
from .state import LibraryState


@dataclass(frozen=True)
class LibraryNodeContext:
    config: ChatConfig
    llm: LLMClient
    retriever: Retriever
    book_lookup: Retriever


def intent_classifier_node(state: LibraryState, context: LibraryNodeContext) -> dict:
    query = state["query"]
    try:
        intent = context.llm.classify_library_intent(query)
    except Exception:
        intent = _fallback_classify(query)
    subgraph = _intent_to_subgraph(intent)
    return {"intent": intent, "subgraph": subgraph}


def retrieval_understand_node(state: LibraryState, context: LibraryNodeContext) -> dict:
    return {"context": {"original_query": state["query"], "intent": state["intent"]}}


def policy_retrieval_node(state: LibraryState, context: LibraryNodeContext) -> dict:
    query = state["query"]
    try:
        docs = context.retriever.search(query, top_k=context.config.retriever_top_k)
        return {"retrieved_docs": docs, "error": None}
    except Exception as exc:
        return {
            "retrieved_docs": [],
            "error": "retriever_unavailable",
            "fallback_response": "抱歉，政策检索服务暂时不可用，请稍后重试。",
        }


def book_lookup_node(state: LibraryState, context: LibraryNodeContext) -> dict:
    query = state["query"]
    try:
        docs = context.book_lookup.search(query, top_k=context.config.retriever_top_k)
        return {"retrieved_docs": docs, "error": None}
    except Exception:
        return {
            "retrieved_docs": [],
            "error": "book_lookup_unavailable",
            "fallback_response": "抱歉，图书检索服务暂时不可用，请稍后重试。",
        }


def recommend_retrieve_node(state: LibraryState, context: LibraryNodeContext) -> dict:
    return book_lookup_node(state, context)


def format_response_node(state: LibraryState, context: LibraryNodeContext) -> dict:
    error = state.get("error")
    if error:
        fallback = state.get("fallback_response", "服务异常，请稍后重试。")
        return {"response": fallback, "sources": []}
    docs = state.get("retrieved_docs", [])
    response = context.llm.format_library_response(state["intent"], state["query"], docs)
    sources = [
        {
            "type": doc.get("metadata", {}).get("source", "unknown"),
            "title": doc.get("metadata", {}).get("title", ""),
            "id": doc.get("metadata", {}).get("id", ""),
        }
        for doc in docs
    ]
    return {"response": response, "sources": sources, "error": None}


def reservation_stub_node(state: LibraryState, context: LibraryNodeContext) -> dict:
    msg = context.llm.stub_message(state["intent"])
    return {"response": msg, "sources": [], "error": None}


def profile_stub_node(state: LibraryState, context: LibraryNodeContext) -> dict:
    msg = context.llm.stub_message(state["intent"])
    return {"response": msg, "sources": [], "error": None}


def direct_answer_node(state: LibraryState, context: LibraryNodeContext) -> dict:
    intent = state["intent"]
    if intent == "greeting":
        return {"response": "您好！我是图书馆智能助手，可以帮您检索图书、查询政策、推荐书籍。请问有什么可以帮您的？", "sources": []}
    return {"response": "抱歉，我没有理解您的问题，请换个方式描述一下？", "sources": []}


# --- internal helpers ---

def _intent_to_subgraph(intent: str) -> str:
    mapping = {
        "search_book": "retrieval",
        "recommend_book": "retrieval",
        "policy_query": "retrieval",
        "book_seat": "reservation",
        "query_appointment": "reservation",
        "cancel_appointment": "reservation",
        "profile_query": "profile",
        "greeting": "direct",
        "other": "direct",
    }
    return mapping.get(intent, "direct")


def _fallback_classify(query: str) -> str:
    lowered = query.lower()
    if any(w in lowered for w in ["书", "book", "找", "推荐", "检索"]):
        return "search_book"
    if any(w in lowered for w in ["几点", "开门", "关门", "借", "罚款", "规则"]):
        return "policy_query"
    if any(w in lowered for w in ["座位", "预约", "取消"]):
        return "book_seat"
    return "other"
```

- [ ] **Step 2: Commit**

```bash
git add app/library_agents/nodes.py
git commit -m "feat: add library nodes — intent, retrieval, stub, direct_answer"
```

---

### Task 8: Library Graph — 主图 + retrieval 子图

**Files:**
- Create: `app/library_agents/graph.py`

- [ ] **Step 1: Write `app/library_agents/graph.py`**

```python
from __future__ import annotations

from langgraph.graph import END, START, StateGraph

from .nodes import (
    LibraryNodeContext,
    book_lookup_node,
    direct_answer_node,
    format_response_node,
    intent_classifier_node,
    policy_retrieval_node,
    profile_stub_node,
    recommend_retrieve_node,
    reservation_stub_node,
    retrieval_understand_node,
)
from .state import LibraryState


def build_library_graph(context: LibraryNodeContext):
    # --- main graph ---
    graph = StateGraph(LibraryState)

    graph.add_node("intent_classifier", lambda s: intent_classifier_node(s, context))
    graph.add_node("retrieval_subgraph", _build_retrieval_subgraph(context))
    graph.add_node("reservation_stub", lambda s: reservation_stub_node(s, context))
    graph.add_node("profile_stub", lambda s: profile_stub_node(s, context))
    graph.add_node("direct_answer", lambda s: direct_answer_node(s, context))

    graph.add_edge(START, "intent_classifier")
    graph.add_conditional_edges(
        "intent_classifier",
        _route_by_subgraph,
        {
            "retrieval": "retrieval_subgraph",
            "reservation": "reservation_stub",
            "profile": "profile_stub",
            "direct": "direct_answer",
        },
    )
    graph.add_edge("retrieval_subgraph", END)
    graph.add_edge("reservation_stub", END)
    graph.add_edge("profile_stub", END)
    graph.add_edge("direct_answer", END)

    return graph.compile()


def _build_retrieval_subgraph(context: LibraryNodeContext):
    sub = StateGraph(LibraryState)

    sub.add_node("understand_query", lambda s: retrieval_understand_node(s, context))
    sub.add_node("policy_retrieve", lambda s: policy_retrieval_node(s, context))
    sub.add_node("book_lookup", lambda s: book_lookup_node(s, context))
    sub.add_node("recommend_retrieve", lambda s: recommend_retrieve_node(s, context))
    sub.add_node("format_response", lambda s: format_response_node(s, context))
    sub.add_node("error_response", lambda s: _error_response_node(s))

    sub.add_edge(START, "understand_query")
    sub.add_conditional_edges(
        "understand_query",
        _route_retrieval_branch,
        {
            "policy": "policy_retrieve",
            "book": "book_lookup",
            "recommend": "recommend_retrieve",
        },
    )
    sub.add_edge("policy_retrieve", "format_response")
    sub.add_edge("book_lookup", "format_response")
    sub.add_edge("recommend_retrieve", "format_response")
    sub.add_conditional_edges(
        "format_response",
        _route_after_format,
        {
            "error": "error_response",
            "done": END,
        },
    )
    sub.add_edge("error_response", END)

    return sub.compile()


def _route_by_subgraph(state: LibraryState) -> str:
    return state.get("subgraph", "direct")


def _route_retrieval_branch(state: LibraryState) -> str:
    intent = state.get("intent", "search_book")
    mapping = {
        "search_book": "book",
        "recommend_book": "recommend",
        "policy_query": "policy",
    }
    return mapping.get(intent, "book")


def _route_after_format(state: LibraryState) -> str:
    if state.get("error"):
        return "error"
    return "done"


def _error_response_node(state: LibraryState) -> dict:
    msg = state.get("fallback_response", "服务异常，请稍后重试。")
    return {"response": msg, "sources": []}
```

- [ ] **Step 2: Commit**

```bash
git add app/library_agents/graph.py
git commit -m "feat: add library graph — main graph + retrieval subgraph"
```

---

### Task 9: ChatService — 组装 + SSE 桥接

**Files:**
- Create: `app/backend/service/chat_service.py`

- [ ] **Step 1: Write `app/backend/service/chat_service.py`**

```python
from __future__ import annotations

import asyncio
from threading import Lock, Thread
from typing import AsyncIterator

from research_agents.adapters.llm import RuleBasedLLMClient
from library_agents.config import ChatConfig
from library_agents.graph import build_library_graph
from library_agents.nodes import LibraryNodeContext
from library_agents.retrieval.protocol import StubRetriever
from library_agents.state import create_initial_library_state


class ChatService:
    def __init__(self):
        self._lock = Lock()
        self._initialized = False
        self._app = None
        self._config = ChatConfig()

    def _ensure_initialized(self) -> None:
        if self._initialized:
            return
        with self._lock:
            if self._initialized:
                return
            context = LibraryNodeContext(
                config=self._config,
                llm=RuleBasedLLMClient(),
                retriever=StubRetriever(),
                book_lookup=StubRetriever(),
            )
            self._app = build_library_graph(context)
            self._initialized = True

    def _invoke_sync(self, query: str, user_id: str | None, history: list[dict] | None) -> dict:
        self._ensure_initialized()
        state = create_initial_library_state(
            query=query,
            user_id=user_id,
            chat_history=history,
        )
        result = self._app.invoke(state)
        return {
            "intent": result.get("intent", "other"),
            "response": result.get("response", ""),
            "sources": result.get("sources", []),
            "subgraph": result.get("subgraph", "direct"),
        }

    def _invoke_sync_stream(self, query: str, user_id: str | None, history: list[dict] | None, emit) -> dict:
        self._ensure_initialized()
        state = create_initial_library_state(
            query=query,
            user_id=user_id,
            chat_history=history,
        )
        for update in self._app.stream(state, stream_mode="updates"):
            if not isinstance(update, dict):
                continue
            for node_name, node_output in update.items():
                if isinstance(node_output, dict):
                    if node_output.get("intent"):
                        emit({"type": "intent", "data": node_output["intent"]})
                    if node_output.get("response"):
                        content = node_output["response"]
                        # simulate token-by-token streaming
                        for i in range(0, len(content), 3):
                            emit({"type": "token", "content": content[i:i+3]})
                        emit({"type": "done", "intent": node_output.get("intent", "other"),
                              "response": content,
                              "sources": node_output.get("sources", [])})
        return {"intent": "other", "response": "", "sources": []}

    async def chat(self, query: str, user_id: str | None = None, history: list[dict] | None = None) -> dict:
        return await asyncio.to_thread(self._invoke_sync, query, user_id, history)

    async def chat_stream(self, query: str, user_id: str | None = None, history: list[dict] | None = None) -> AsyncIterator[dict]:
        queue: asyncio.Queue[dict] = asyncio.Queue()
        loop = asyncio.get_running_loop()

        def emit(event: dict) -> None:
            asyncio.run_coroutine_threadsafe(queue.put(event), loop)

        def worker() -> None:
            try:
                self._invoke_sync_stream(query, user_id, history, emit)
            except Exception as exc:
                emit({"type": "error", "code": "internal", "message": str(exc)})
            finally:
                emit({"type": "__done__"})

        Thread(target=worker, daemon=True).start()
        while True:
            event = await queue.get()
            if event.get("type") == "__done__":
                break
            yield event


_CHAT_SERVICE: ChatService | None = None


def get_chat_service() -> ChatService:
    global _CHAT_SERVICE
    if _CHAT_SERVICE is None:
        _CHAT_SERVICE = ChatService()
    return _CHAT_SERVICE
```

- [ ] **Step 2: Commit**

```bash
git add app/backend/service/chat_service.py
git commit -m "feat: add ChatService with SSE streaming support"
```

---

### Task 10: Chat Router + Book Router

**Files:**
- Create: `app/backend/router/chat_router.py`
- Create: `app/backend/router/book_router.py`

- [ ] **Step 1: Write `chat_router.py`**

```python
from __future__ import annotations

import json

from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse

from backend.schemas.chat import ChatRequest, ChatResponse
from backend.service.chat_service import ChatService, get_chat_service


router = APIRouter(prefix="/api/v1/chat", tags=["chat"])


@router.post("", response_model=ChatResponse)
async def chat(
    payload: ChatRequest,
    service: ChatService = Depends(get_chat_service),
) -> ChatResponse:
    result = await service.chat(
        query=payload.query,
        user_id=payload.user_id,
        history=payload.history,
    )
    return ChatResponse(**result)


@router.post("/stream")
async def chat_stream(
    payload: ChatRequest,
    service: ChatService = Depends(get_chat_service),
) -> StreamingResponse:
    async def event_stream():
        async for event in service.chat_stream(
            query=payload.query,
            user_id=payload.user_id,
            history=payload.history,
        ):
            yield _sse(event)

    return StreamingResponse(event_stream(), media_type="text/event-stream")


def _sse(event: dict) -> str:
    event_type = event.get("type", "message")
    data = json.dumps(event, ensure_ascii=False)
    return f"event: {event_type}\ndata: {data}\n\n"
```

- [ ] **Step 2: Write `book_router.py`**

```python
from __future__ import annotations

from fastapi import APIRouter, Query

from backend.schemas.chat import BookSearchResult


router = APIRouter(prefix="/api/v1/books", tags=["books"])


@router.get("", response_model=list[BookSearchResult])
async def search_books(q: str = Query(..., min_length=1), limit: int = Query(default=10, ge=1, le=50)):
    """Simple book search — returns stub results until DB is configured."""
    return [
        BookSearchResult(
            id=f"STUB-{idx}",
            title=f"Placeholder: {q}",
            author="Unknown",
            location="待配置",
            available=0,
        )
        for idx in range(1, min(limit, 3) + 1)
    ]
```

- [ ] **Step 3: Commit**

```bash
git add app/backend/router/chat_router.py app/backend/router/book_router.py
git commit -m "feat: add chat and book API routers"
```

---

### Task 11: Register Routers in app_main

**Files:**
- Modify: `app/app_main.py`

- [ ] **Step 1: Edit `app/app_main.py` — add imports and router registration**

Add after the existing router imports:

```python
from backend.router.chat_router import router as chat_router
from backend.router.book_router import router as book_router
```

Add after `app.include_router(research_router)`:

```python
    app.include_router(chat_router)
    app.include_router(book_router)
```

- [ ] **Step 2: Verify startup**

```bash
cd app && python -c "from app_main import app; print('Routes:', [r.path for r in app.routes])"
```

Expected output includes: `/api/v1/chat`, `/api/v1/chat/stream`, `/api/v1/books`

- [ ] **Step 3: Commit**

```bash
git add app/app_main.py
git commit -m "feat: register chat and book routers in app_main"
```

---

### Task 12: Integration Tests — Graph Routing

**Files:**
- Create: `tests/test_library_graph.py`

- [ ] **Step 1: Write integration tests**

```python
import pytest
from research_agents.adapters.llm import RuleBasedLLMClient
from library_agents.config import ChatConfig
from library_agents.graph import build_library_graph
from library_agents.nodes import LibraryNodeContext
from library_agents.retrieval.protocol import StubRetriever
from library_agents.state import create_initial_library_state


@pytest.fixture
def context():
    return LibraryNodeContext(
        config=ChatConfig(),
        llm=RuleBasedLLMClient(),
        retriever=StubRetriever(),
        book_lookup=StubRetriever(),
    )


@pytest.fixture
def app(context):
    return build_library_graph(context)


@pytest.mark.parametrize("query,expected_intent,expected_subgraph", [
    ("有没有《三体》", "search_book", "retrieval"),
    ("推荐几本小说", "recommend_book", "retrieval"),
    ("图书馆几点关门", "policy_query", "retrieval"),
    ("我要预约座位", "book_seat", "reservation"),
    ("我的预约记录", "query_appointment", "reservation"),
    ("取消我的预约", "cancel_appointment", "reservation"),
    ("我的借阅记录", "profile_query", "profile"),
    ("你好", "greeting", "direct"),
    ("今天天气怎么样", "other", "direct"),
])
def test_intent_routing(app, query, expected_intent, expected_subgraph):
    state = create_initial_library_state(query=query)
    result = app.invoke(state)
    assert result["intent"] == expected_intent
    assert result["subgraph"] == expected_subgraph


def test_retrieval_produces_response(app):
    state = create_initial_library_state(query="有没有《三体》")
    result = app.invoke(state)
    assert result["response"]
    assert len(result["response"]) > 0


def test_stub_returns_placeholder(app):
    state = create_initial_library_state(query="我要预约座位")
    result = app.invoke(state)
    assert "开发中" in result["response"]


def test_greeting_returns_friendly(app):
    state = create_initial_library_state(query="你好")
    result = app.invoke(state)
    assert "您好" in result["response"] or "图书馆" in result["response"]


def test_empty_query_handled(app):
    state = create_initial_library_state(query="")
    result = app.invoke(state)
    assert result["intent"] is not None
    assert result["response"] is not None
```

- [ ] **Step 2: Run tests**

```bash
python -m pytest tests/test_library_graph.py -v
```
Expected: 14 PASS

- [ ] **Step 3: Commit**

```bash
git add tests/test_library_graph.py
git commit -m "test: add graph routing integration tests (14 cases)"
```

---

### Task 13: E2E Tests — Chat API

**Files:**
- Create: `tests/test_chat_api.py`

- [ ] **Step 1: Write E2E tests**

```python
import json
import pytest
from fastapi.testclient import TestClient
from app_main import app


client = TestClient(app)


@pytest.mark.parametrize("query", [
    "有没有《三体》",
    "图书馆几点开门",
    "你好",
])
def test_chat_sync_returns_valid_response(query):
    resp = client.post("/api/v1/chat", json={"query": query})
    assert resp.status_code == 200
    data = resp.json()
    assert "intent" in data
    assert "response" in data
    assert len(data["response"]) > 0
    assert "sources" in data
    assert "subgraph" in data


def test_chat_stream_returns_sse():
    with client.stream("POST", "/api/v1/chat/stream", json={"query": "有没有《三体》"}) as resp:
        assert resp.status_code == 200
        events = []
        for line in resp.iter_lines():
            if line:
                events.append(line)
        assert len(events) > 0


def test_chat_missing_query_returns_422():
    resp = client.post("/api/v1/chat", json={})
    assert resp.status_code == 422


def test_health_endpoint():
    resp = client.get("/api/v1/health")
    assert resp.status_code == 200


def test_books_endpoint():
    resp = client.get("/api/v1/books?q=Python")
    assert resp.status_code == 200
    data = resp.json()
    assert isinstance(data, list)
```

- [ ] **Step 2: Run tests**

```bash
python -m pytest tests/test_chat_api.py -v
```
Expected: 6 PASS

- [ ] **Step 3: Commit**

```bash
git add tests/test_chat_api.py
git commit -m "test: add E2E chat and book API tests"
```

---

### Task 14: Frontend — Chat Interface

**Files:**
- Modify: `front/src/App.vue`
- Modify: `front/index.html`

- [ ] **Step 1: Edit `front/index.html` — update title**

Change title to: `<title>图书馆智能助手</title>`

- [ ] **Step 2: Rewrite `front/src/App.vue`**

(See complete Vue file below — in actual file, replace entire content)

```vue
<script setup lang="ts">
import { nextTick, ref } from 'vue'

type SSEEvent = {
  type: 'intent' | 'token' | 'done' | 'error'
  intent?: string
  content?: string
  data?: string
  response?: string
  sources?: Array<Record<string, unknown>>
}

type Message = {
  id: string
  role: 'user' | 'assistant'
  content: string
  intent?: string
  sources?: Array<Record<string, unknown>>
}

const query = ref('')
const loading = ref(false)
const error = ref('')
const messages = ref<Message[]>([
  {
    id: 'welcome',
    role: 'assistant',
    content: '您好！我是图书馆智能助手。\n\n可以帮您：\n- 检索图书（"有没有《三体》"）\n- 推荐书籍（"推荐几本小说"）\n- 政策咨询（"图书馆几点关门"）\n- 座位预约（"我要预约座位"）',
  },
])
const messageListRef = ref<HTMLElement | null>(null)

const sendMessage = async () => {
  const text = query.value.trim()
  if (!text || loading.value) return

  loading.value = true
  error.value = ''
  messages.value.push({ id: crypto.randomUUID(), role: 'user', content: text })
  query.value = ''
  await scrollToBottom()

  const assistantId = crypto.randomUUID()
  messages.value.push({ id: assistantId, role: 'assistant', content: '', intent: '', sources: [] })
  await scrollToBottom()

  try {
    const response = await fetch('/api/v1/chat/stream', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ query: text }),
    })
    if (!response.ok || !response.body) {
      throw new Error(`Request failed: ${response.status}`)
    }

    const reader = response.body.getReader()
    const decoder = new TextDecoder('utf-8')
    let buffer = ''

    while (true) {
      const { done, value } = await reader.read()
      if (done) break
      buffer += decoder.decode(value, { stream: true })
      const frames = buffer.split('\n\n')
      buffer = frames.pop() || ''
      for (const frame of frames) {
        const lines = frame.split('\n')
        let eventType = ''
        let data = ''
        for (const line of lines) {
          if (line.startsWith('event: ')) eventType = line.slice(7)
          if (line.startsWith('data: ')) data = line.slice(6)
        }
        if (!data) continue
        try {
          const event = JSON.parse(data) as SSEEvent
          const msg = messages.value.find((m) => m.id === assistantId)
          if (!msg) continue
          if (eventType === 'intent') {
            msg.intent = event.data || event.intent
          }
          if (eventType === 'token') {
            msg.content += event.content || ''
          }
          if (eventType === 'done') {
            msg.intent = event.intent || msg.intent
            msg.content = event.response || msg.content
            msg.sources = event.sources || []
          }
          if (eventType === 'error') {
            msg.content += `\n[错误: ${event.content || '服务异常'}]`
          }
        } catch {
          // skip unparseable frames
        }
      }
      await scrollToBottom()
    }
  } catch (err) {
    const message = err instanceof Error ? err.message : 'Request failed'
    error.value = message
    const msg = messages.value.find((m) => m.id === assistantId)
    if (msg) msg.content = `请求失败: ${message}`
  } finally {
    loading.value = false
    await scrollToBottom()
  }
}

const scrollToBottom = async () => {
  await nextTick()
  if (messageListRef.value) {
    messageListRef.value.scrollTop = messageListRef.value.scrollHeight
  }
}

const intentLabel = (intent: string) => {
  const map: Record<string, string> = {
    search_book: '图书检索',
    recommend_book: '推荐',
    policy_query: '政策咨询',
    book_seat: '座位预约',
    query_appointment: '预约查询',
    cancel_appointment: '取消预约',
    profile_query: '读者画像',
    greeting: '问候',
    other: '其他',
  }
  return map[intent] || intent
}
</script>

<template>
  <main class="shell">
    <aside class="sidebar">
      <h1>图书馆智能助手</h1>
      <p class="description">AI 驱动的图书馆服务系统</p>
      <div class="features">
        <span>检索</span><span>推荐</span><span>政策咨询</span><span>座位预约</span>
      </div>
    </aside>

    <section class="workspace">
      <div ref="messageListRef" class="messages">
        <article v-for="message in messages" :key="message.id" :class="['message', message.role]">
          <div class="avatar">{{ message.role === 'user' ? '我' : 'AI' }}</div>
          <div class="bubble">
            <span v-if="message.intent" class="intent-tag">{{ intentLabel(message.intent) }}</span>
            <pre>{{ message.content }}</pre>
          </div>
        </article>
      </div>

      <form class="composer" @submit.prevent="sendMessage">
        <textarea v-model="query" :disabled="loading" rows="2" placeholder="输入您的问题..." />
        <button :disabled="loading || !query.trim()">{{ loading ? '...' : '发送' }}</button>
      </form>
      <p v-if="error" class="error">{{ error }}</p>
    </section>
  </main>
</template>
```

- [ ] **Step 3: Verify frontend builds**

```bash
cd front && npm run build
```
Expected: builds without errors.

- [ ] **Step 4: Commit**

```bash
git add front/src/App.vue front/index.html
git commit -m "feat: rewrite frontend as library chat interface"
```

---

### Task 15: Docker Setup

**Files:**
- Create: `Dockerfile`
- Create: `docker-compose.yml`
- Create: `.dockerignore`

- [ ] **Step 1: Write `.dockerignore`**

```
.venv/
__pycache__/
*.pyc
node_modules/
dist/
.git/
.superpowers/
.env
*.log
chroma_data/
```

- [ ] **Step 2: Write `Dockerfile`**

```dockerfile
FROM python:3.11-slim

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

RUN pip install --no-cache-dir chromadb sqlalchemy psycopg2-binary redis celery

COPY . .

EXPOSE 8000

CMD ["uvicorn", "app.app_main:app", "--host", "0.0.0.0", "--port", "8000"]
```

- [ ] **Step 3: Write `docker-compose.yml`**

```yaml
version: "3.8"

services:
  app:
    build: .
    ports:
      - "8000:8000"
    environment:
      - APP_ENV=production
      - CONFIG_PATH=/app/config.example.json
    depends_on:
      - postgres
      - redis
    restart: unless-stopped

  postgres:
    image: postgres:15-alpine
    environment:
      POSTGRES_USER: library
      POSTGRES_PASSWORD: library123
      POSTGRES_DB: library
    ports:
      - "5432:5432"
    volumes:
      - pgdata:/var/lib/postgresql/data
    restart: unless-stopped

  redis:
    image: redis:7-alpine
    ports:
      - "6379:6379"
    restart: unless-stopped

volumes:
  pgdata:
```

- [ ] **Step 4: Commit**

```bash
git add Dockerfile docker-compose.yml .dockerignore
git commit -m "feat: add Docker deployment (Dockerfile + docker-compose)"
```

---

### Task 16: Update Requirements

**Files:**
- Modify: `requirements.txt`

- [ ] **Step 1: Add dependencies to `requirements.txt`**

Add to the end:

```
chromadb>=0.4.0
sqlalchemy>=2.0.0
psycopg2-binary>=2.9.0
redis>=5.0.0
celery>=5.3.0
pytest>=8.0.0
httpx>=0.27.0
```

- [ ] **Step 2: Commit**

```bash
git add requirements.txt
git commit -m "chore: add Phase 1 dependencies to requirements.txt"
```

---

### Task 17: Final Integration Verification

- [ ] **Step 1: Run all tests**

```bash
python -m pytest tests/ -v
```
Expected: all tests pass.

- [ ] **Step 2: Verify backend starts**

```bash
cd app && timeout 5 uvicorn app_main:app --port 8000 || true
```
Expected: no import errors.

- [ ] **Step 3: Quick smoke test**

```bash
# Start backend in background
cd app && uvicorn app_main:app --port 8000 &
sleep 2
# Test endpoints
curl -s http://127.0.0.1:8000/api/v1/health
curl -s -X POST http://127.0.0.1:8000/api/v1/chat -H "Content-Type: application/json" -d '{"query":"有没有《三体》"}'
curl -s "http://127.0.0.1:8000/api/v1/books?q=Python"
# Kill background uvicorn
kill %1
```

Expected: health returns OK, chat returns JSON with intent/response/sources, books returns array.

- [ ] **Step 4: Verify Docker build**

```bash
docker compose build
```
Expected: image builds successfully.

- [ ] **Step 5: Final commit if any fixes**

```bash
git add -A && git commit -m "chore: final integration verification fixes"
```

---

### Task 18: Push to Remotes

- [ ] **Step 1: Push both branches**

```bash
git push github main
git push github dev
git push gitee main
git push gitee dev
```

---

## Dependency Order

```
Task 1 (State) ─┬─→ Task 3 (Retriever Protocol) ─→ Task 6 (Retrievers)
                │
                ├─→ Task 4 (Schemas)
                │
                ├─→ Task 2 (Config) ─┐
                │                    ├─→ Task 7 (Nodes) ─→ Task 8 (Graph) ─→ Task 9 (ChatService)
                └─→ Task 5 (LLM) ────┘                                          │
                                                                                ├─→ Task 10 (Routers)
                                                                                │        │
                                                                                │        └─→ Task 11 (app_main)
                                                                                │
                                                                                └─→ Task 12 (Integration Tests) ─→ Task 13 (E2E Tests)
                                                                                                                         │
                Task 14 (Frontend) ←─────────────────────────────────────────────────────────────────────────────────────┤
                Task 15 (Docker)   ←─────────────────────────────────────────────────────────────────────────────────────┤
                Task 16 (Requirements) ←─────────────────────────────────────────────────────────────────────────────────┤
                Task 17 (Verification) ←─────────────────────────────────────────────────────────────────────────────────┘
                                                                                                                         │
                Task 18 (Push) ←─────────────────────────────────────────────────────────────────────────────────────────┘
```

Tasks 1-4 can run in parallel. Tasks 7+8 depend on 2,3,5. Tasks 12,13 (tests) depend on graph + routers.
