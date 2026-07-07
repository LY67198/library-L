"""profile_subgraph 集成测试 — 验证子图三节点链路"""
import pytest
from unittest.mock import patch, MagicMock
from datetime import datetime, timezone
from agents.llm import RuleBasedLLMClient
from agents.config import ChatConfig
from agents.graph import build_library_graph
from agents.nodes import LibraryNodeContext
from agents.retrieval.protocol import StubRetriever
from agents.state import create_initial_library_state


def _build_context():
    return LibraryNodeContext(
        config=ChatConfig(),
        llm=RuleBasedLLMClient(),
        retriever=StubRetriever(),
        book_lookup=StubRetriever(),
        session_factory=None,
    )


def test_profile_query_unauthenticated():
    """未登录时返回提示"""
    context = _build_context()
    app = build_library_graph(context)
    state = create_initial_library_state(query="我的个人信息", user_id=None)
    result = app.invoke(state)
    assert "请先登录" in result["response"]


def test_profile_query_returns_response_with_mock():
    """mock asyncio.run 返回预置数据，验证完整链路"""
    context = _build_context()
    context = LibraryNodeContext(
        config=ChatConfig(),
        llm=RuleBasedLLMClient(),
        retriever=StubRetriever(),
        book_lookup=StubRetriever(),
        session_factory=MagicMock(),
    )
    app = build_library_graph(context)

    canned_user = MagicMock()
    canned_user.display_name = "测试读者"
    canned_user.student_id = "R010"
    canned_user.username = "reader10"

    canned_result = {
        "user": canned_user,
        "appointments": [],
        "borrow_records": [],
    }

    with patch("agents.nodes.asyncio") as mock_aio:
        mock_aio.run.return_value = canned_result
        state = create_initial_library_state(query="我的个人信息", user_id="test-user-id")
        result = app.invoke(state)

    assert "测试读者" in result["response"]
    assert "R010" in result["response"]


def test_profile_query_with_borrow_history_mock():
    """mock 返回含借阅记录的数据"""
    context = LibraryNodeContext(
        config=ChatConfig(),
        llm=RuleBasedLLMClient(),
        retriever=StubRetriever(),
        book_lookup=StubRetriever(),
        session_factory=MagicMock(),
    )
    app = build_library_graph(context)

    canned_user = MagicMock()
    canned_user.display_name = "借阅读者"
    canned_user.student_id = "R011"
    canned_user.username = "reader11"

    mock_book = MagicMock()
    mock_book.title = "三体"

    mock_br = MagicMock()
    mock_br.id = "br-1"
    mock_br.book = mock_book
    mock_br.borrowed_at = datetime(2026, 6, 1, tzinfo=timezone.utc)
    mock_br.due_at = datetime(2026, 7, 1, tzinfo=timezone.utc)
    mock_br.returned_at = None
    mock_br.status = MagicMock()
    mock_br.status.value = "borrowed"

    canned_result = {
        "user": canned_user,
        "appointments": [],
        "borrow_records": [mock_br],
    }

    with patch("agents.nodes.asyncio") as mock_aio:
        mock_aio.run.return_value = canned_result
        state = create_initial_library_state(query="我的借阅记录", user_id="test-user-id")
        result = app.invoke(state)

    assert "三体" in result["response"]


def test_profile_query_empty_history_mock():
    """mock 空借阅记录，验证不出现开发中提示"""
    context = LibraryNodeContext(
        config=ChatConfig(),
        llm=RuleBasedLLMClient(),
        retriever=StubRetriever(),
        book_lookup=StubRetriever(),
        session_factory=MagicMock(),
    )
    app = build_library_graph(context)

    canned_user = MagicMock()
    canned_user.display_name = "空记录读者"
    canned_user.student_id = "R012"
    canned_user.username = "reader12"

    canned_result = {
        "user": canned_user,
        "appointments": [],
        "borrow_records": [],
    }

    with patch("agents.nodes.asyncio") as mock_aio:
        mock_aio.run.return_value = canned_result
        state = create_initial_library_state(query="我借过什么书", user_id="test-user-id")
        result = app.invoke(state)

    assert len(result["response"]) > 0
    assert "开发中" not in result["response"]


def test_profile_query_db_unavailable():
    """session_factory 为 None 时返回错误提示"""
    context = _build_context()
    app = build_library_graph(context)
    state = create_initial_library_state(query="我的借阅记录", user_id="test-user-id")
    result = app.invoke(state)
    assert "暂不可用" in result["response"] or "请先登录" in result["response"]
