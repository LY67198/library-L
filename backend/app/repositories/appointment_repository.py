from __future__ import annotations

from datetime import datetime
from uuid import UUID

from sqlalchemy import and_, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Appointment, AppointmentStatus


class AppointmentRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def list_for_user(self, user_id: int, tenant_id: UUID) -> list[Appointment]:
        stmt = (
            select(Appointment)
            .where(Appointment.user_id == user_id, Appointment.tenant_id == tenant_id)
            .order_by(Appointment.start_time.desc())
        )
        return list((await self.session.execute(stmt)).scalars().all())

    async def get_by_id(self, appt_id: int, tenant_id: UUID) -> Appointment | None:
        stmt = select(Appointment).where(
            Appointment.id == appt_id, Appointment.tenant_id == tenant_id
        )
        return (await self.session.execute(stmt)).scalar_one_or_none()

    async def check_time_conflict(
        self,
        tenant_id: UUID,
        seat_id: int,
        start_time: datetime,
        end_time: datetime,
    ) -> bool:
        """Return True if any non-cancelled appointment overlaps the window for this seat."""
        stmt = select(Appointment.id).where(
            and_(
                Appointment.tenant_id == tenant_id,
                Appointment.seat_id == seat_id,
                Appointment.status.in_(
                    [AppointmentStatus.pending.value, AppointmentStatus.confirmed.value, AppointmentStatus.active.value]
                ),
                Appointment.start_time < end_time,
                Appointment.end_time > start_time,
            )
        ).limit(1)
        return (await self.session.execute(stmt)).scalar_one_or_none() is not None

    async def create(
        self,
        *,
        tenant_id: UUID,
        user_id: int,
        seat_id: int,
        start_time: datetime,
        end_time: datetime,
    ) -> Appointment:
        appt = Appointment(
            tenant_id=tenant_id,
            user_id=user_id,
            resource_type="seat",
            resource_id=seat_id,
            seat_id=seat_id,
            start_time=start_time,
            end_time=end_time,
            status=AppointmentStatus.confirmed.value,
            version=0,
        )
        self.session.add(appt)
        await self.session.flush()
        await self.session.refresh(appt)
        return appt

    async def cancel_with_version(
        self,
        appt: Appointment,
        *,
        expected_version: int,
        reason: str | None = None,
    ) -> bool:
        """Optimistic-lock UPDATE; returns False if version mismatch."""
        now = datetime.utcnow()
        stmt = (
            update(Appointment)
            .where(Appointment.id == appt.id, Appointment.version == expected_version)
            .values(
                status=AppointmentStatus.cancelled.value,
                cancelled_at=now,
                cancel_reason=reason,
                version=expected_version + 1,
            )
        )
        result = await self.session.execute(stmt)
        return result.rowcount > 0