"""座位预约路由 — 提供我的预约查询、单条预约查询、预约座位、取消预约等接口。"""
from __future__ import annotations

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, get_db
from app.models import User
from app.schemas.appointment import (
    AppointmentCancelRequest,
    AppointmentCreate,
    AppointmentResponse,
)
from app.services.appointment_service import AppointmentService

router = APIRouter(prefix="/appointments", tags=["appointments"])


@router.get("", response_model=list[AppointmentResponse])
async def list_my_appointments(
    request: Request,
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[User, Depends(get_current_user)],
) -> list[AppointmentResponse]:
    """查询当前登录用户的所有预约记录。

    参数:
        request: FastAPI 请求对象,用于读取当前租户上下文。
        db: 异步数据库会话。
        user: 当前登录用户,作为查询条件。

    返回值:
        list[AppointmentResponse]: 当前用户的全部预约列表。
    """
    tenant_id: UUID = request.state.tenant_id
    service = AppointmentService(db)
    items = await service.list_for_user(user.id, tenant_id)
    return [AppointmentResponse.model_validate(a) for a in items]


@router.get("/{appt_id}", response_model=AppointmentResponse)
async def get_appointment(
    appt_id: int,
    request: Request,
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[User, Depends(get_current_user)],
) -> AppointmentResponse:
    """按 ID 查询单条预约详情 — 仅本人或图书管理员可查看。

    参数:
        appt_id: 预约主键 ID(路径参数)。
        request: FastAPI 请求对象,用于读取当前租户上下文。
        db: 异步数据库会话。
        user: 当前登录用户,用于所有者/角色校验。

    返回值:
        AppointmentResponse: 预约详情。

    抛出:
        Forbidden: 当用户既非预约本人又非图书管理员时抛出。
    """
    tenant_id: UUID = request.state.tenant_id
    service = AppointmentService(db)
    appt = await service.get(appt_id, tenant_id)
    if appt.user_id != user.id and user.role not in ("librarian", "admin"):
        from app.core.exceptions import Forbidden
        raise Forbidden("Cannot view another user's appointment")
    return AppointmentResponse.model_validate(appt)


@router.post("", response_model=AppointmentResponse, status_code=201)
async def book_seat(
    request: Request,
    payload: AppointmentCreate,
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[User, Depends(get_current_user)],
) -> AppointmentResponse:
    """预约座位 — 为当前用户在指定时间段创建一条座位预约。

    参数:
        request: FastAPI 请求对象,用于读取当前租户上下文。
        payload: 预约创建请求体,包含 seat_id / start_time / end_time。
        db: 异步数据库会话。
        user: 当前登录用户,作为预约所有人。

    返回值:
        AppointmentResponse: 新建后的预约详情。
    """
    tenant_id: UUID = request.state.tenant_id
    service = AppointmentService(db)
    appt = await service.book_seat(
        tenant_id=tenant_id,
        user_id=user.id,
        seat_id=payload.seat_id,
        start_time=payload.start_time,
        end_time=payload.end_time,
    )
    return AppointmentResponse.model_validate(appt)


@router.post("/{appt_id}/cancel", response_model=AppointmentResponse)
async def cancel_appointment(
    appt_id: int,
    payload: AppointmentCancelRequest,
    request: Request,
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[User, Depends(get_current_user)],
) -> AppointmentResponse:
    """取消座位预约 — 标记为取消状态并记录原因。

    参数:
        appt_id: 预约主键 ID(路径参数)。
        payload: 取消请求体,包含可选的取消原因 reason。
        request: FastAPI 请求对象,用于读取当前租户上下文。
        db: 异步数据库会话。
        user: 当前登录用户,作为操作者。

    返回值:
        AppointmentResponse: 取消后的预约详情。
    """
    tenant_id: UUID = request.state.tenant_id
    service = AppointmentService(db)
    appt = await service.cancel(appt_id, tenant_id, user.id, reason=payload.reason)
    return AppointmentResponse.model_validate(appt)
