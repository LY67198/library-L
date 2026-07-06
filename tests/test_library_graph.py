"""图路由集成测试 — 9 意图路由 + 检索产出 + Stub 兜底"""

import pytest
from research_agents.adapters.llm import RuleBasedLLMClient
from agents.config import ChatConfig
from agents.graph import build_library_graph
from agents.nodes import LibraryNodeContext
from agents.retrieval.protocol import StubRetriever
from agents.state import create_initial_library_state


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


@pytest.mark.parametrize(
    "query,expected_intent,expected_subgraph",
    [
        ("有没有《三体》", "search_book", "retrieval"),
        ("推荐几本小说", "recommend_book", "retrieval"),
        ("图书馆几点关门", "policy_query", "retrieval"),
        ("我要预约座位", "book_seat", "reservation"),
        ("我的预约记录", "query_appointment", "reservation"),
        ("取消我的预约", "cancel_appointment", "reservation"),
        ("我的借阅记录", "profile_query", "profile"),
        ("你好", "greeting", "direct"),
        ("今天天气怎么样", "other", "direct"),
    ],
)
def test_intent_routing(app, query, expected_intent, expected_subgraph):
    state = create_initial_library_state(query=query)
    result = app.invoke(state)
    assert result["intent"] == expected_intent, f"query={query}"
    assert result["subgraph"] == expected_subgraph, f"query={query}"


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
