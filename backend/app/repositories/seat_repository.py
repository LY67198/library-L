from __future__ import annotations

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Seat


class SeatRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def get_by_id(self, seat_id: int, tenant_id: UUID) -> Seat | None:
        stmt = select(Seat).where(Seat.id == seat_id, Seat.tenant_id == tenant_id)
        return (await self.session.execute(stmt)).scalar_one_or_none()

    async def list_all(self, tenant_id: UUID) -> list[Seat]:
        stmt = select(Seat).where(Seat.tenant_id == tenant_id).order_by(Seat.floor, Seat.code)
        return list((await self.session.execute(stmt)).scalars().all())

    async def list_by_floor(self, tenant_id: UUID, floor: str) -> list[Seat]:
        stmt = (
            select(Seat)
            .where(Seat.tenant_id == tenant_id, Seat.floor == floor)
            .order_by(Seat.code)
        )
        return list((await self.session.execute(stmt)).scalars().all())