"""API Key 认证 — ContextVar + 中间件 + 用户查找"""

from __future__ import annotations

import contextvars
import logging

from fastapi import Request, Response
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from core.database import get_session_factory
from models import User

logger = logging.getLogger(__name__)

# 请求级 ContextVar — 每个 HTTP 请求独立
_current_mcp_user: contextvars.ContextVar[User | None] = contextvars.ContextVar(
    "mcp_current_user", default=None
)

# 待绑定映射 — SSE 握手时暂存，首次 POST /messages 时绑定
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


async def mcp_auth_middleware(request: Request, call_next) -> Response:
    """FastAPI HTTP 中间件 — 从 Authorization header 提取 API Key 并注入 ContextVar

    MCP SSE 流程：
    1. GET /sse → 带 Authorization header → 验证成功
    2. POST /messages?session_id=xxx → 从 _pending_api_keys 恢复

    中间件对每个请求运行，保证 ContextVar 始终在请求生命周期内有效。
    """
    from urllib.parse import parse_qs

    user: User | None = None

    # 方式 1：Authorization header
    auth_header = request.headers.get("Authorization", "")
    if auth_header.startswith("Bearer "):
        api_key = auth_header[7:].strip()
        if api_key:
            user = await _lookup_user_by_api_key(api_key)

    # 方式 2：session_id 映射（POST /messages 兜底）
    if user is None:
        parsed = parse_qs(request.url.query)
        session_ids = parsed.get("session_id", [])
        if session_ids:
            sid = session_ids[0]
            api_key = _pending_api_keys.get(sid)
            if api_key:
                user = await _lookup_user_by_api_key(api_key)

    # 方式 3：sessionId header（某些客户端使用）
    if user is None:
        sid = request.headers.get("mcp-session-id") or request.headers.get("Mcp-Session-Id")
        if sid:
            api_key = _pending_api_keys.get(sid)
            if api_key:
                user = await _lookup_user_by_api_key(api_key)

    _current_mcp_user.set(user)
    response = await call_next(request)
    return response


def bind_session_user(session_id: str, user: User) -> None:
    """将 MCP session_id 与用户绑定，供后续 POST /messages 恢复认证上下文。"""
    _pending_api_keys[session_id] = user.api_key
