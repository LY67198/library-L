"""座位预约业务逻辑"""

from __future__ import annotations

from datetime import date as Date, datetime, timezone

from sqlalchemy import and_, select
from sqlalchemy.ext.asyncio import AsyncSession

from core.cleanup import cleanup_expired_slots as _do_cleanup
from core.lock import SeatLock
from models import (
    Appointment,
    AppointmentStatus,
    Floor,
    Seat,
    SeatStatus,
    SeatTimeSlot,
    TimeSlot,
    Zone,
)


class SeatService:

    def __init__(self, db: AsyncSession, lock: SeatLock):
        self._db = db
        self._lock = lock

    async def _cleanup_expired_slots(self, date_value: Date, slot: str) -> None:
        """懒清理：释放过期未签到的预约。委托 core.cleanup。"""
        await _do_cleanup(self._db, self._lock, date_value, slot)

    async def list_seats(
        self,
        floor_id: int | None = None,
        zone_id: int | None = None,
        date_value: Date | None = None,
        slot: str | None = None,
        user_id: str | None = None,
    ) -> list[dict]:
        """查询座位列表，支持筛选。懒清理过期预约。"""
        if date_value and slot:
            await self._cleanup_expired_slots(date_value, slot)

        query = (
            select(Seat, Zone.id, Zone.name, Floor.id, Floor.name)
            .join(Zone, Seat.zone_id == Zone.id)
            .join(Floor, Zone.floor_id == Floor.id)
        )

        if floor_id:
            query = query.where(Floor.id == floor_id)
        if zone_id:
            query = query.where(Zone.id == zone_id)

        result = await self._db.execute(query)
        rows = result.all()

        seats = []
        for seat, zone_id, zone_name, floor_id, floor_name in rows:
            status = "available"
            booked_by_me = False

            if date_value and slot:
                slot_enum = TimeSlot(slot)
                sts_result = await self._db.execute(
                    select(SeatTimeSlot).where(
                        and_(
                            SeatTimeSlot.seat_id == seat.id,
                            SeatTimeSlot.date == date_value,
                            SeatTimeSlot.slot == slot_enum,
                        )
                    )
                )
                existing = sts_result.scalar_one_or_none()
                if existing:
                    status = "booked"
                    if user_id and existing.user_id == user_id:
                        booked_by_me = True

            if seat.status == SeatStatus.disabled:
                status = "disabled"

            seats.append({
                "seat_id": seat.id,
                "floor_id": floor_id,
                "floor_name": floor_name,
                "zone_id": zone_id,
                "zone_name": zone_name,
                "seat_number": seat.seat_number,
                "status": status,
                "booked_by_me": booked_by_me,
            })

        return seats

    async def book_seat(
        self, seat_id: str, user_id: str, date_value: Date, slot: str
    ) -> dict:
        """预约座位 — Redis 抢锁 + PG 写入 + 双重保障"""
        date_str = str(date_value)

        try:
            TimeSlot(slot)
        except ValueError:
            raise ValueError("无效的时段")

        today = datetime.now(timezone.utc).date()
        if date_value < today:
            raise ValueError("不能预约过去的日期")

        result = await self._db.execute(select(Seat).where(Seat.id == seat_id))
        seat = result.scalar_one_or_none()
        if seat is None:
            raise ValueError("座位不存在")
        if seat.status == SeatStatus.disabled:
            raise ValueError("该座位暂不可用")

        slot_enum = TimeSlot(slot)
        existing = await self._db.execute(
            select(SeatTimeSlot).where(
                and_(
                    SeatTimeSlot.user_id == user_id,
                    SeatTimeSlot.date == date_value,
                    SeatTimeSlot.slot == slot_enum,
                )
            )
        )
        if existing.scalar_one_or_none():
            raise ValueError("同一时段已有预约")

        acquired = await self._lock.acquire(seat_id, date_str, slot, user_id, ttl=30)
        if not acquired:
            raise ValueError("座位已被预约")

        try:
            sts = SeatTimeSlot(
                seat_id=seat_id,
                date=date_value,
                slot=slot_enum,
                user_id=user_id,
            )
            self._db.add(sts)

            appt = Appointment(
                user_id=user_id,
                seat_id=seat_id,
                date=date_value,
                slot=slot_enum,
                status=AppointmentStatus.booked,
            )
            self._db.add(appt)
            await self._db.commit()
            await self._db.refresh(appt)

            zone_result = await self._db.execute(
                select(Zone.name, Floor.name)
                .join(Floor, Zone.floor_id == Floor.id)
                .where(Zone.id == seat.zone_id)
            )
            zone_name, floor_name = zone_result.one()

            return {
                "appointment_id": appt.id,
                "seat_id": seat_id,
                "floor_name": floor_name,
                "zone_name": zone_name,
                "seat_number": seat.seat_number,
                "date": date_str,
                "slot": slot,
            }
        except Exception:
            await self._lock.release(seat_id, date_str, slot)
            raise

    async def list_appointments(self, user_id: str) -> list[dict]:
        """查询用户的所有预约"""
        result = await self._db.execute(
            select(Appointment, Seat.seat_number, Zone.name, Floor.name)
            .join(Seat, Appointment.seat_id == Seat.id)
            .join(Zone, Seat.zone_id == Zone.id)
            .join(Floor, Zone.floor_id == Floor.id)
            .where(Appointment.user_id == user_id)
            .order_by(Appointment.created_at.desc())
        )
        rows = result.all()

        return [
            {
                "appointment_id": appt.id,
                "seat_id": appt.seat_id,
                "floor_name": floor_name,
                "zone_name": zone_name,
                "seat_number": seat_number,
                "date": str(appt.date),
                "slot": appt.slot.value,
                "status": appt.status.value,
            }
            for appt, seat_number, zone_name, floor_name in rows
        ]

    async def cancel_appointment(self, appointment_id: str, user_id: str) -> dict:
        """取消预约"""
        result = await self._db.execute(
            select(Appointment).where(
                and_(
                    Appointment.id == appointment_id,
                    Appointment.user_id == user_id,
                )
            )
        )
        appt = result.scalar_one_or_none()
        if appt is None:
            raise ValueError("预约记录不存在")

        if appt.status == AppointmentStatus.cancelled:
            raise ValueError("预约已取消")

        if appt.status == AppointmentStatus.expired:
            raise ValueError("预约已过期")

        date_str = str(appt.date)
        slot_str = appt.slot.value
        await self._lock.release(appt.seat_id, date_str, slot_str)

        sts_result = await self._db.execute(
            select(SeatTimeSlot).where(
                and_(
                    SeatTimeSlot.seat_id == appt.seat_id,
                    SeatTimeSlot.date == appt.date,
                    SeatTimeSlot.slot == appt.slot,
                )
            )
        )
        sts = sts_result.scalar_one_or_none()
        if sts:
            await self._db.delete(sts)

        appt.status = AppointmentStatus.cancelled
        await self._db.commit()

        return {
            "appointment_id": appointment_id,
            "status": "cancelled",
        }
