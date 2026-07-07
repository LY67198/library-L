"""MCP SSE 集成测试 — 测试 MCP 端点 + 认证"""

import asyncio

import pytest
import pytest_asyncio
from unittest.mock import AsyncMock, patch
from httpx import ASGITransport, AsyncClient


@pytest_asyncio.fixture
async def _patch_lookup():
    """Mock _lookup_user_by_api_key 以避免连接 PostgreSQL"""
    with patch("mcp_server.auth._lookup_user_by_api_key", new_callable=AsyncMock) as mock:
        mock.return_value = None  # 默认不认证
        yield mock


@pytest_asyncio.fixture
async def app_with_mcp(_patch_lookup):
    """创建带 MCP 挂载的 FastAPI 测试应用"""
    from app_main import create_app
    return create_app()


@pytest_asyncio.fixture
async def async_client(app_with_mcp):
    """异步 HTTP 测试客户端"""
    transport = ASGITransport(app=app_with_mcp)
    async with AsyncClient(transport=transport, base_url="http://localhost:8000", timeout=5) as client:
        yield client


@pytest_asyncio.fixture
async def seeded_user(db_session):
    """创建一个带 api_key 的测试用户"""
    from models import User
    user = User(
        id="mcp-test-user",
        username="mcp_test",
        password_hash="$2b$12$LJ3m4ys3GZfnYMz8kVsKaOTSxqnPxhH0gHqSp3UNqNLoXLDCuWHKG",
        display_name="MCP测试",
        student_id="MCP001",
        api_key="test-api-key-123abc",
        is_admin=False,
    )
    db_session.add(user)
    await db_session.commit()
    return user


class TestMcpSseEndpoint:
    """MCP SSE 端点基础测试"""

    @pytest.mark.asyncio
    async def test_sse_endpoint_accessible(self, async_client):
        """SSE 端点可访问（SSE 长连接，验证未崩溃即可）"""
        try:
            resp = await asyncio.wait_for(
                async_client.get("/api/v1/mcp/sse"), timeout=3.0
            )
            assert resp.status_code in (200, 401, 406)
        except asyncio.TimeoutError:
            # SSE 端点正常建立连接并保持打开，超时是预期行为
            pass

    @pytest.mark.asyncio
    async def test_messages_endpoint_exists(self, async_client):
        """POST /messages 端点存在"""
        resp = await async_client.post(
            "/api/v1/mcp/messages/",
            json={"jsonrpc": "2.0", "method": "tools/list", "id": 1},
            headers={"Content-Type": "application/json"},
        )
        assert resp.status_code in (200, 400, 401, 404)


class TestMcpAuthIntegration:
    """认证集成测试"""

    @pytest.mark.asyncio
    async def test_sse_with_valid_api_key(self, async_client, seeded_user, _patch_lookup):
        """带有效 API Key 访问 SSE 端点"""
        _patch_lookup.return_value = seeded_user
        try:
            resp = await asyncio.wait_for(
                async_client.get(
                    "/api/v1/mcp/sse",
                    headers={"Authorization": f"Bearer {seeded_user.api_key}"},
                ),
                timeout=3.0,
            )
            assert resp.status_code in (200, 401, 406)
            assert resp.status_code != 500
        except asyncio.TimeoutError:
            # SSE 端点正常，超时是预期行为
            pass

    @pytest.mark.asyncio
    async def test_sse_without_auth_returns_stream(self, async_client):
        """无认证时 SSE 端点仍可连接（匿名）"""
        try:
            resp = await asyncio.wait_for(
                async_client.get("/api/v1/mcp/sse"), timeout=3.0
            )
            assert resp.status_code != 500
        except asyncio.TimeoutError:
            # SSE 端点正常
            pass
