"""MCP auth 模块测试"""

import pytest
from fastapi import FastAPI, Request
from fastapi.testclient import TestClient
from sqlalchemy import select

from mcp_server.auth import (
    McpAuthMiddleware,
    _pending_api_keys,
    bind_session_user,
    get_current_mcp_user,
)
from models import User


class TestGetCurrentMcpUser:
    """ContextVar 读写"""

    def test_returns_none_when_not_set(self):
        assert get_current_mcp_user() is None


class TestBindSessionUser:
    """session_id ↔ user 绑定"""

    def test_binds_user_to_session(self):
        _pending_api_keys.clear()
        user = User(
            id="u1", username="test", password_hash="x",
            display_name="Test", student_id="S001", api_key="key123"
        )
        bind_session_user("session-1", user)
        assert "session-1" in _pending_api_keys
        assert _pending_api_keys["session-1"] == "key123"


class TestMcpAuthMiddleware:
    """API Key 认证中间件"""

    def test_no_auth_header_does_not_crash(self):
        """无 Authorization header 时不报错，返回 None"""
        app = FastAPI()
        app.add_middleware(McpAuthMiddleware)

        @app.get("/test")
        async def test_endpoint(request: Request):
            u = get_current_mcp_user()
            assert u is None
            return {"ok": True}

        client = TestClient(app)
        resp = client.get("/test")
        assert resp.status_code == 200
