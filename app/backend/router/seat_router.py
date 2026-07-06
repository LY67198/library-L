"""座位预约接口 — 搜索/预约/取消/查询"""

from __future__ import annotations

from datetime import date as Date

import redis.asyncio as aioredis
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from backend.config.settings import get_settings
from backend.schemas.seat import (
    AppointmentItem,
    AppointmentListResponse,
    BookRequest,
    BookResponse,
    CancelResponse,
    SeatItem,
    SeatListResponse,
)
from backend.service.seat_service import SeatService
from core.database import get_db
from core.deps import get_required_user
from core.lock import SeatLock
from models import User

router = APIRouter(prefix="/api/v1", tags=["seats"])

_REDIS_CLIENT: aioredis.Redis | None = None
_SEAT_LOCK: SeatLock | None = None


def _get_redis() -> aioredis.Redis:
    global _REDIS_CLIENT
    if _REDIS_CLIENT is None:
        settings = get_settings()
        _REDIS_CLIENT = aioredis.from_url(settings.redis_url, decode_responses=False)
    return _REDIS_CLIENT


async def get_seat_lock() -> SeatLock:
    """FastAPI 依赖 — 提供 SeatLock 实例（测试时可 override）"""
    global _SEAT_LOCK
    if _SEAT_LOCK is None:
        _SEAT_LOCK = SeatLock(_get_redis())
    return _SEAT_LOCK


@router.get("/seats", response_model=SeatListResponse)
async def list_seats(
    floor_id: int | None = Query(None),
    zone_id: int | None = Query(None),
    date: str | None = Query(None, description="YYYY-MM-DD"),
    slot: str | None = Query(None, pattern="^(morning|afternoon|evening)$"),
    db: AsyncSession = Depends(get_db),
    lock: SeatLock = Depends(get_seat_lock),
    user: User | None = Depends(get_required_user),
):
    date_value = Date.fromisoformat(date) if date else None
    service = SeatService(db, lock)
    seats = await service.list_seats(
        floor_id=floor_id,
        zone_id=zone_id,
        date_value=date_value,
        slot=slot,
        user_id=user.id if user else None,
    )
    return SeatListResponse(seats=[SeatItem(**s) for s in seats])


@router.post("/seats/{seat_id}/book", response_model=BookResponse)
async def book_seat(
    seat_id: str,
    payload: BookRequest,
    db: AsyncSession = Depends(get_db),
    lock: SeatLock = Depends(get_seat_lock),
    user: User = Depends(get_required_user),
):
    date_value = Date.fromisoformat(payload.date)
    service = SeatService(db, lock)
    try:
        result = await service.book_seat(seat_id, user.id, date_value, payload.slot)
        return BookResponse(**result)
    except ValueError as e:
        msg = str(e)
        if "已被预约" in msg:
            raise HTTPException(
                status_code=409,
                detail={"error": "seat_already_booked", "message": msg},
            )
        if "暂不可用" in msg:
            raise HTTPException(
                status_code=422,
                detail={"error": "seat_disabled", "message": msg},
            )
        if "同一时段已有" in msg:
            raise HTTPException(
                status_code=422,
                detail={"error": "duplicate_booking", "message": msg},
            )
        if "过去的日期" in msg:
            raise HTTPException(
                status_code=422,
                detail={"error": "past_slot", "message": msg},
            )
        raise HTTPException(status_code=422, detail=msg)


@router.get("/appointments", response_model=AppointmentListResponse)
async def list_appointments(
    db: AsyncSession = Depends(get_db),
    lock: SeatLock = Depends(get_seat_lock),
    user: User = Depends(get_required_user),
):
    service = SeatService(db, lock)
    appointments = await service.list_appointments(user.id)
    return AppointmentListResponse(
        appointments=[AppointmentItem(**a) for a in appointments]
    )


@router.post("/appointments/{appointment_id}/cancel", response_model=CancelResponse)
async def cancel_appointment(
    appointment_id: str,
    db: AsyncSession = Depends(get_db),
    lock: SeatLock = Depends(get_seat_lock),
    user: User = Depends(get_required_user),
):
    service = SeatService(db, lock)
    try:
        result = await service.cancel_appointment(appointment_id, user.id)
        return CancelResponse(**result)
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))
