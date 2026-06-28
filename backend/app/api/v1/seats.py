"""座位查询路由 — 提供按全部、按楼层、按可用状态等维度的座位列表查询接口。"""
from __future__ import annotations

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, get_db
from app.models import User
from app.repositories.seat_repository import SeatRepository
from app.schemas.seat import SeatListResponse, SeatResponse

router = APIRouter(prefix="/seats", tags=["seats"])


@router.get("", response_model=SeatListResponse)
async def list_seats(
    request: Request,
    db: Annotated[AsyncSession, Depends(get_db)],
    _: Annotated[User, Depends(get_current_user)],
) -> SeatListResponse:
    """查询当前租户下的全部座位。

    参数:
        request: FastAPI 请求对象,用于读取当前租户上下文。
        db: 异步数据库会话。
        _: 当前登录用户(此处仅用于鉴权占位)。

    返回值:
        SeatListResponse: 全部座位列表与总数。
    """
    tenant_id: UUID = request.state.tenant_id
    repo = SeatRepository(db)
    items = await repo.list_all(tenant_id)
    return SeatListResponse(
        items=[SeatResponse.model_validate(s) for s in items],
        total=len(items),
    )


@router.get("/floor/{floor}", response_model=SeatListResponse)
async def list_seats_by_floor(
    floor: str,
    request: Request,
    db: Annotated[AsyncSession, Depends(get_db)],
    _: Annotated[User, Depends(get_current_user)],
) -> SeatListResponse:
    """按楼层查询座位列表。

    参数:
        floor: 楼层标识(路径参数)。
        request: FastAPI 请求对象,用于读取当前租户上下文。
        db: 异步数据库会话。
        _: 当前登录用户(此处仅用于鉴权占位)。

    返回值:
        SeatListResponse: 指定楼层的座位列表与总数。
    """
    tenant_id: UUID = request.state.tenant_id
    repo = SeatRepository(db)
    items = await repo.list_by_floor(tenant_id, floor)
    return SeatListResponse(
        items=[SeatResponse.model_validate(s) for s in items],
        total=len(items),
    )


@router.get("/available", response_model=SeatListResponse)
async def list_available_seats(
    request: Request,
    db: Annotated[AsyncSession, Depends(get_db)],
    _: Annotated[User, Depends(get_current_user)],
) -> SeatListResponse:
    """查询当前可用的座位 — 仅返回 status 为 "available" 的座位。

    参数:
        request: FastAPI 请求对象,用于读取当前租户上下文。
        db: 异步数据库会话。
        _: 当前登录用户(此处仅用于鉴权占位)。

    返回值:
        SeatListResponse: 当前可预约的座位列表与总数。
    """
    tenant_id: UUID = request.state.tenant_id
    repo = SeatRepository(db)
    all_seats = await repo.list_all(tenant_id)
    available = [s for s in all_seats if s.status == "available"]
    return SeatListResponse(
        items=[SeatResponse.model_validate(s) for s in available],
        total=len(available),
    )
