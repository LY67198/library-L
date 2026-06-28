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
    tenant_id: UUID = request.state.tenant_id
    service = AppointmentService(db)
    appt = await service.cancel(appt_id, tenant_id, user.id, reason=payload.reason)
    return AppointmentResponse.model_validate(appt)