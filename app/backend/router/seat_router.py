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
    BookingResponse,
    SeatItem,
    SeatListResponse,
)
from backend.service.seat_service import SeatService
from core.database import get_db
from core.deps import get_current_user, get_required_user
from core.lock import SeatLock
from models import User

router = APIRouter(tags=["seats"])

_REDIS_CLIENT: aioredis.Redis | None = None
_SEAT_LOCK: SeatLock | None = None


def _get_redis() -> aioredis.Redis:
    global _REDIS_CLIENT
    if _REDIS_CLIENT is None:
        settings = get_settings()
        _REDIS_CLIENT = aioredis.from_url(settings.redis_url, decode_responses=False, protocol=2)
    return _REDIS_CLIENT


async def get_seat_lock() -> SeatLock:
    """FastAPI 依赖 — 提供 SeatLock 实例（测试时可 override）"""
    global _SEAT_LOCK
    if _SEAT_LOCK is None:
        _SEAT_LOCK = SeatLock(_get_redis())
    return _SEAT_LOCK


@router.get("/api/v1/seats", response_model=SeatListResponse)
async def list_seats(
    floor_id: int | None = Query(None),
    zone_id: int | None = Query(None),
    date: str | None = Query(None, description="YYYY-MM-DD"),
    slot: str | None = Query(None, pattern="^(morning|afternoon|evening)$"),
    offset: int = Query(default=0, ge=0),
    limit: int = Query(default=100, ge=1, le=200),
    db: AsyncSession = Depends(get_db),
    lock: SeatLock = Depends(get_seat_lock),
    user: User | None = Depends(get_current_user),
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
    total = len(seats)
    paginated = seats[offset:offset + limit]
    return SeatListResponse(
        seats=[SeatItem(**s) for s in paginated],
        total=total,
        offset=offset,
        limit=limit,
    )


@router.post("/api/v1/seats/{seat_id}/bookings", response_model=BookingResponse)
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
        return BookingResponse(**result)
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


@router.get("/api/v1/appointments", response_model=AppointmentListResponse)
async def list_appointments(
    offset: int = Query(default=0, ge=0),
    limit: int = Query(default=100, ge=1, le=200),
    db: AsyncSession = Depends(get_db),
    lock: SeatLock = Depends(get_seat_lock),
    user: User = Depends(get_required_user),
):
    service = SeatService(db, lock)
    appointments = await service.list_appointments(user.id)
    total = len(appointments)
    paginated = appointments[offset:offset + limit]
    return AppointmentListResponse(
        appointments=[AppointmentItem(**a) for a in paginated],
        total=total,
        offset=offset,
        limit=limit,
    )


@router.delete("/api/v1/appointments/{appointment_id}", status_code=status.HTTP_204_NO_CONTENT)
async def cancel_appointment(
    appointment_id: str,
    db: AsyncSession = Depends(get_db),
    lock: SeatLock = Depends(get_seat_lock),
    user: User = Depends(get_required_user),
):
    service = SeatService(db, lock)
    try:
        await service.cancel_appointment(appointment_id, user.id)
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))
