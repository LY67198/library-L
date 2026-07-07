"""MCP Server — FastMCP 实例 + SSE 传输 + FastAPI 挂载"""

from __future__ import annotations

import logging

from mcp.server.fastmcp import FastMCP

from mcp_server.auth import bind_session_user, get_current_mcp_user
from mcp_server.tools import (
    book_seat_impl,
    cancel_appointment_impl,
    list_appointments_impl,
    list_seats_impl,
    search_books_impl,
)

logger = logging.getLogger(__name__)

# FastMCP 实例
mcp = FastMCP(name="图书馆智能服务系统")


def _register_tools() -> None:
    """向 FastMCP 注册 5 个 Tool，使用 name 参数去掉 _impl 后缀"""
    mcp.tool(name="search_books")(search_books_impl)
    mcp.tool(name="list_seats")(list_seats_impl)
    mcp.tool(name="book_seat")(book_seat_impl)
    mcp.tool(name="list_appointments")(list_appointments_impl)
    mcp.tool(name="cancel_appointment")(cancel_appointment_impl)


def create_mcp_sse_app():
    """创建可挂载到 FastAPI 的 ASGI 应用

    Returns:
        Starlette ASGI app — 通过 app.mount() 挂载到 FastAPI
    """
    _register_tools()
    return mcp.sse_app()
