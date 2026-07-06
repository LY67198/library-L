"""图书馆 Agent 节点实现 — 意图分类、检索、Stub、直接回答"""

from __future__ import annotations

from dataclasses import dataclass

from research_agents.adapters.llm import LLMClient
from .config import ChatConfig
from .retrieval.protocol import Retriever
from .state import LibraryState


@dataclass(frozen=True)
class LibraryNodeContext:
    """节点依赖注入容器"""

    config: ChatConfig
    llm: LLMClient
    retriever: Retriever
    book_lookup: Retriever


# --- 主图节点 ---

def intent_classifier_node(state: LibraryState, context: LibraryNodeContext) -> dict:
    """9 分类意图识别，LLM 失败时关键词兜底"""
    query = state["query"]
    try:
        intent = context.llm.classify_library_intent(query)
    except Exception:
        intent = _fallback_classify(query)
    subgraph = _intent_to_subgraph(intent)
    return {"intent": intent, "subgraph": subgraph}


# --- 检索子图节点 ---

def retrieval_understand_node(state: LibraryState, context: LibraryNodeContext) -> dict:
    """提取查询条件，确定检索类型"""
    return {"context": {"original_query": state["query"], "intent": state["intent"]}}


def policy_retrieval_node(state: LibraryState, context: LibraryNodeContext) -> dict:
    """ChromaDB 向量检索政策文档"""
    query = state["query"]
    try:
        docs = context.retriever.search(query, top_k=context.config.retriever_top_k)
        return {"retrieved_docs": docs, "error": None}
    except Exception:
        return {
            "retrieved_docs": [],
            "error": "retriever_unavailable",
            "fallback_response": "抱歉，政策检索服务暂时不可用，请稍后重试。",
        }


def book_lookup_node(state: LibraryState, context: LibraryNodeContext) -> dict:
    """PostgreSQL 图书字段查询"""
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
    """推荐检索 — Phase 1 复用图书检索"""
    return book_lookup_node(state, context)


def format_response_node(state: LibraryState, context: LibraryNodeContext) -> dict:
    """格式化检索结果为用户可读回复"""
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


# --- Stub 节点 ---

def reservation_stub_node(state: LibraryState, context: LibraryNodeContext) -> dict:
    """座位预约 Stub — 返回开发中提示"""
    msg = context.llm.stub_message(state["intent"])
    return {"response": msg, "sources": [], "error": None}


def profile_stub_node(state: LibraryState, context: LibraryNodeContext) -> dict:
    """读者画像 Stub — 返回开发中提示"""
    msg = context.llm.stub_message(state["intent"])
    return {"response": msg, "sources": [], "error": None}


def direct_answer_node(state: LibraryState, context: LibraryNodeContext) -> dict:
    """问候和兜底直接回答"""
    intent = state["intent"]
    if intent == "greeting":
        return {
            "response": "您好！我是图书馆智能助手，可以帮您检索图书、查询政策、推荐书籍。请问有什么可以帮您的？",
            "sources": [],
        }
    return {"response": "抱歉，我没有理解您的问题，请换个方式描述一下？", "sources": []}


# --- 内部辅助函数 ---

def _intent_to_subgraph(intent: str) -> str:
    """意图 → 子图路由映射"""
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
    """LLM 不可用时的关键词兜底分类"""
    lowered = query.lower()
    if any(w in lowered for w in ["书", "book", "找", "推荐", "检索"]):
        return "search_book"
    if any(w in lowered for w in ["几点", "开门", "关门", "借", "罚款", "规则"]):
        return "policy_query"
    if any(w in lowered for w in ["座位", "预约", "取消"]):
        return "book_seat"
    return "other"
