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
    """Currently-available seats (status='available')."""
    tenant_id: UUID = request.state.tenant_id
    repo = SeatRepository(db)
    all_seats = await repo.list_all(tenant_id)
    available = [s for s in all_seats if s.status == "available"]
    return SeatListResponse(
        items=[SeatResponse.model_validate(s) for s in available],
        total=len(available),
    )