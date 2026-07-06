"""图书馆 Agent 图编排 — 主图 + retrieval 子图"""

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
    """构建图书馆 Agent 主图，返回编译后的可执行图"""
    graph = StateGraph(LibraryState)

    # --- 节点注册 ---
    graph.add_node("intent_classifier", lambda s: intent_classifier_node(s, context))
    graph.add_node("retrieval_subgraph", _build_retrieval_subgraph(context))
    graph.add_node("reservation_stub", lambda s: reservation_stub_node(s, context))
    graph.add_node("profile_stub", lambda s: profile_stub_node(s, context))
    graph.add_node("direct_answer", lambda s: direct_answer_node(s, context))

    # --- 路由连线 ---
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
    """构建检索子图：understand → retrieve → format"""
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


# --- 路由函数 ---

def _route_by_subgraph(state: LibraryState) -> str:
    """主图路由：根据意图分发到对应子图"""
    return state.get("subgraph", "direct")


def _route_retrieval_branch(state: LibraryState) -> str:
    """检索子图路由：根据意图选择检索方式"""
    intent = state.get("intent", "search_book")
    mapping = {
        "search_book": "book",
        "recommend_book": "recommend",
        "policy_query": "policy",
    }
    return mapping.get(intent, "book")


def _route_after_format(state: LibraryState) -> str:
    """格式化后路由：有错误则走错误节点"""
    if state.get("error"):
        return "error"
    return "done"


def _error_response_node(state: LibraryState) -> dict:
    """错误降级节点 — 返回兜底消息"""
    msg = state.get("fallback_response", "服务异常，请稍后重试。")
    return {"response": msg, "sources": []}
