"""图书馆智能问答共享状态定义"""

from __future__ import annotations

from typing import TypedDict


class LibraryState(TypedDict):
    """图书馆聊天共享状态 — 所有节点通过此字典传递数据"""

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
    """创建初始化的 LibraryState"""
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
