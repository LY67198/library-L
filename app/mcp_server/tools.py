"""MCP Tool 实现 — 5 个图书馆核心能力"""

from __future__ import annotations

import logging
from datetime import date as Date
from typing import Annotated

from core.database import get_session_factory
from core.lock import SeatLock
from backend.service.book_service import BookService
from backend.service.seat_service import SeatService
from mcp_server.auth import get_current_mcp_user

logger = logging.getLogger(__name__)

# Redis 锁实例 — 懒初始化
_lock: SeatLock | None = None


def _get_lock() -> SeatLock:
    global _lock
    if _lock is None:
        import redis.asyncio as aioredis
        from backend.config.settings import get_settings
        redis_client = aioredis.from_url(get_settings().redis_url, decode_responses=False, protocol=2)
        _lock = SeatLock(redis_client)
    return _lock


def _require_user():
    """获取当前用户，未认证则抛出错误"""
    user = get_current_mcp_user()
    if user is None:
        raise ValueError("未认证 — 请在 MCP 客户端配置 Authorization: Bearer <api_key>")
    return user


# ─── search_books ───

async def search_books_impl(
    query: Annotated[str, "搜索关键词，支持书名/作者/ISBN 模糊搜索"],
    category: Annotated[str | None, "分类代码，如 A、B、TP 等"] = None,
    offset: int = 0,
    limit: int = 10,
) -> dict:
    """检索图书馆馆藏图书，支持书名/作者/ISBN 模糊搜索 + 分类筛选"""
    factory = get_session_factory()
    async with factory() as db:
        service = BookService(db)
        books, total = await service.list_books(q=query, category=category or "", offset=offset, limit=limit)
        items = [
            {
                "id": b.id,
                "title": b.title,
                "author": b.author,
                "isbn": b.isbn or "",
                "publisher": b.publisher or "",
                "publish_year": b.publish_year,
                "category": b.category or "",
                "location": b.location or "",
                "total": b.total,
                "available": b.available,
            }
            for b in books
        ]
        return {"items": items, "total": total}


# ─── list_seats ───

async def list_seats_impl(
    floor_id: Annotated[int | None, "楼层 ID"] = None,
    zone_id: Annotated[int | None, "区域 ID"] = None,
    date: Annotated[str | None, "日期，格式 YYYY-MM-DD"] = None,
    slot: Annotated[str | None, "时段: morning / afternoon / evening"] = None,
    offset: int = 0,
    limit: int = 100,
) -> dict:
    """查询图书馆可预约座位，支持按楼层/区域/日期/时段筛选"""
    _require_user()
    date_value = Date.fromisoformat(date) if date else None
    factory = get_session_factory()
    async with factory() as db:
        service = SeatService(db, _get_lock())
        user = get_current_mcp_user()
        seats = await service.list_seats(
            floor_id=floor_id,
            zone_id=zone_id,
            date_value=date_value,
            slot=slot,
            user_id=user.id if user else None,
        )
        total = len(seats)
        paginated = seats[offset:offset + limit]
        return {"seats": paginated, "total": total, "offset": offset, "limit": limit}


# ─── book_seat ───

async def book_seat_impl(
    seat_id: Annotated[str, "座位 ID（UUID）"],
    date: Annotated[str, "日期，格式 YYYY-MM-DD"],
    slot: Annotated[str, "时段: morning / afternoon / evening"],
) -> dict:
    """预约指定座位，需要提供座位ID、日期和时段"""
    user = _require_user()
    date_value = Date.fromisoformat(date)
    factory = get_session_factory()
    async with factory() as db:
        service = SeatService(db, _get_lock())
        try:
            result = await service.book_seat(seat_id, user.id, date_value, slot)
            return {
                "appointment_id": result["appointment_id"],
                "seat_id": result["seat_id"],
                "floor_name": result["floor_name"],
                "zone_name": result["zone_name"],
                "seat_number": result["seat_number"],
                "date": result["date"],
                "slot": result["slot"],
                "status": "booked",
            }
        except ValueError as e:
            return {"error": str(e)}


# ─── list_appointments ───

async def list_appointments_impl(
    offset: int = 0,
    limit: int = 100,
) -> dict:
    """查询当前用户的预约记录"""
    user = _require_user()
    factory = get_session_factory()
    async with factory() as db:
        service = SeatService(db, _get_lock())
        appointments = await service.list_appointments(user.id)
        total = len(appointments)
        paginated = appointments[offset:offset + limit]
        return {"appointments": paginated, "total": total, "offset": offset, "limit": limit}


# ─── cancel_appointment ───

async def cancel_appointment_impl(
    appointment_id: Annotated[str, "要取消的预约 ID（UUID）"],
) -> dict:
    """取消指定的预约记录"""
    user = _require_user()
    factory = get_session_factory()
    async with factory() as db:
        service = SeatService(db, _get_lock())
        try:
            result = await service.cancel_appointment(appointment_id, user.id)
            return {"success": True, "cancelled_id": result["appointment_id"]}
        except ValueError as e:
            return {"error": str(e)}
