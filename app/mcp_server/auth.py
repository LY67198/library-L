"""API Key 认证 — ContextVar + 纯 ASGI 中间件 + 用户查找"""

from __future__ import annotations

import contextvars
import logging
from urllib.parse import parse_qs

from sqlalchemy import select

from core.database import get_session_factory
from models import User

logger = logging.getLogger(__name__)

# 请求级 ContextVar — 每个 HTTP 请求独立
_current_mcp_user: contextvars.ContextVar[User | None] = contextvars.ContextVar(
    "mcp_current_user", default=None
)

# 待绑定映射 — SSE 握手时暂存，POST /messages 时恢复
_pending_api_keys: dict[str, str] = {}  # session_id → api_key


def get_current_mcp_user() -> User | None:
    """获取当前 MCP 请求上下文中的用户。Tool 调用时使用。"""
    return _current_mcp_user.get()


async def _lookup_user_by_api_key(api_key: str) -> User | None:
    """用 API Key 查库找用户"""
    factory = get_session_factory()
    async with factory() as db:
        result = await db.execute(
            select(User).where(User.api_key == api_key, User.is_active == True)
        )
        return result.scalar_one_or_none()


class McpAuthMiddleware:
    """纯 ASGI 中间件 — 不劫持响应体，兼容 SSE 流式传输

    与 BaseHTTPMiddleware 不同，纯 ASGI 中间件不会读取响应体，
    因此不会破坏 SSE 长连接。只在请求到达时设置 ContextVar。
    """

    def __init__(self, app):
        self._app = app

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            await self._app(scope, receive, send)
            return

        # 解析 headers
        headers = {}
        for key, value in scope.get("headers", []):
            headers[key.decode("latin-1").lower()] = value.decode("latin-1")

        user: User | None = None

        # 方式 1：Authorization header
        auth_header = headers.get("authorization", "")
        if auth_header.startswith("Bearer "):
            api_key = auth_header[7:].strip()
            if api_key:
                user = await _lookup_user_by_api_key(api_key)

        # 方式 2：session_id 映射（POST /messages 兜底）
        if user is None:
            query_string = scope.get("query_string", b"").decode("latin-1")
            parsed = parse_qs(query_string)
            session_ids = parsed.get("session_id", [])
            if session_ids:
                sid = session_ids[0]
                api_key = _pending_api_keys.get(sid)
                if api_key:
                    user = await _lookup_user_by_api_key(api_key)

        # 方式 3：sessionId header（某些客户端使用）
        if user is None:
            sid = headers.get("mcp-session-id") or headers.get("mcp-session-id")
            if sid:
                api_key = _pending_api_keys.get(sid)
                if api_key:
                    user = await _lookup_user_by_api_key(api_key)

        _current_mcp_user.set(user)
        await self._app(scope, receive, send)


def bind_session_user(session_id: str, user: User) -> None:
    """将 MCP session_id 与用户绑定，供后续 POST /messages 恢复认证上下文。"""
    _pending_api_keys[session_id] = user.api_key
