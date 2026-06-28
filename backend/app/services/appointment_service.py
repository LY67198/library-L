from __future__ import annotations

from datetime import datetime, timedelta
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.clients.redis_client import get_redis
from app.core.concurrency import DistributedLock, LockAcquireError, acquire_with_retry
from app.core.exceptions import Conflict, NotFound
from app.models import Appointment
from app.repositories.appointment_repository import AppointmentRepository
from app.repositories.seat_repository import SeatRepository


class AppointmentService:
    def __init__(self, session: AsyncSession):
        self.session = session
        self.repo = AppointmentRepository(session)
        self.seat_repo = SeatRepository(session)

    async def list_for_user(self, user_id: int, tenant_id: UUID) -> list[Appointment]:
        return await self.repo.list_for_user(user_id, tenant_id)

    async def get(self, appt_id: int, tenant_id: UUID) -> Appointment:
        appt = await self.repo.get_by_id(appt_id, tenant_id)
        if appt is None:
            raise NotFound(f"Appointment {appt_id} not found")
        return appt

    async def book_seat(
        self,
        *,
        tenant_id: UUID,
        user_id: int,
        seat_id: int,
        start_time: datetime,
        end_time: datetime,
    ) -> Appointment:
        # Validate seat exists
        seat = await self.seat_repo.get_by_id(seat_id, tenant_id)
        if seat is None:
            raise NotFound(f"Seat {seat_id} not found")
        if end_time <= start_time:
            raise Conflict("end_time must be after start_time")

        # Stage 1: Redis distributed lock on seat
        redis = get_redis()
        lock_key = f"lock:seat:{tenant_id}:{seat_id}"
        try:
            lock = await acquire_with_retry(
                lambda: DistributedLock(redis, key=lock_key, ttl_ms=3000),
                max_retries=3,
            )
        except LockAcquireError:
            raise Conflict("Seat is being booked by another user, please retry")

        try:
            # Stage 2: DB-level conflict check
            conflict = await self.repo.check_time_conflict(
                tenant_id, seat_id, start_time, end_time
            )
            if conflict:
                raise Conflict("Seat is already booked in this time slot")
            return await self.repo.create(
                tenant_id=tenant_id,
                user_id=user_id,
                seat_id=seat_id,
                start_time=start_time,
                end_time=end_time,
            )
        finally:
            await lock.__aexit__(None, None, None)

    async def cancel(
        self,
        appt_id: int,
        tenant_id: UUID,
        user_id: int,
        *,
        reason: str | None = None,
    ) -> Appointment:
        appt = await self.get(appt_id, tenant_id)
        if appt.user_id != user_id:
            raise Conflict("Cannot cancel another user's appointment")
        # Stage 1: Redis lock
        redis = get_redis()
        lock_key = f"lock:appt:{tenant_id}:{appt_id}"
        try:
            lock = await acquire_with_retry(
                lambda: DistributedLock(redis, key=lock_key, ttl_ms=3000),
                max_retries=3,
            )
        except LockAcquireError:
            raise Conflict("Appointment is being modified, please retry")
        try:
            # Stage 2: PG optimistic lock
            ok = await self.repo.cancel_with_version(
                appt, expected_version=appt.version, reason=reason
            )
            if not ok:
                raise Conflict("Appointment was modified concurrently, please retry")
            await self.session.refresh(appt)
            return appt
        finally:
            await lock.__aexit__(None, None, None)