"""E2E 测试 — Chat + Book API 端点"""

import pytest
from fastapi.testclient import TestClient
from app_main import app

client = TestClient(app)


@pytest.mark.parametrize(
    "query",
    [
        "有没有《三体》",
        "图书馆几点开门",
        "你好",
    ],
)
def test_chat_sync_returns_valid_response(query):
    resp = client.post("/api/v1/chat", json={"query": query})
    assert resp.status_code == 200, f"query={query}"
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
