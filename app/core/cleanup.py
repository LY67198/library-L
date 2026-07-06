"""座位预约超时清理 — Celery 与懒清理共用"""

from __future__ import annotations

from datetime import date, datetime, time, timezone

from sqlalchemy import and_, select
from sqlalchemy.ext.asyncio import AsyncSession

from models import Appointment, AppointmentStatus, SeatTimeSlot, TimeSlot

SLOT_TIMES: dict[str, tuple[time, time]] = {
    "morning": (time(0, 0), time(4, 0)),
    "afternoon": (time(5, 0), time(9, 0)),
    "evening": (time(10, 0), time(14, 0)),
}


def _slot_cutoff(date_value: date, slot: str) -> datetime:
    """计算某时段过期截止时间：slot_start + 30min"""
    slot_start, _ = SLOT_TIMES[slot]
    slot_start_dt = datetime.combine(date_value, slot_start, tzinfo=timezone.utc)
    return slot_start_dt.replace(minute=slot_start_dt.minute + 30)


async def cleanup_expired_slots(
    db: AsyncSession,
    lock,  # SeatLock
    date_value: date,
    slot: str | None = None,
) -> int:
    """清理过期未签到的预约。slot=None 则清理所有时段。返回清理条数。"""
    slots_to_check = [slot] if slot else list(SLOT_TIMES.keys())
    now = datetime.now(timezone.utc)
    cleaned = 0

    for s in slots_to_check:
        cutoff = _slot_cutoff(date_value, s)
        if now < cutoff:
            continue

        result = await db.execute(
            select(SeatTimeSlot).join(
                Appointment,
                and_(
                    SeatTimeSlot.seat_id == Appointment.seat_id,
                    SeatTimeSlot.date == Appointment.date,
                    SeatTimeSlot.slot == Appointment.slot,
                ),
            ).where(
                and_(
                    SeatTimeSlot.date == date_value,
                    SeatTimeSlot.slot == TimeSlot(s),
                    Appointment.status == AppointmentStatus.booked,
                    SeatTimeSlot.booked_at < cutoff,
                )
            )
        )
        expired_sts = result.scalars().all()

        for sts in expired_sts:
            await lock.release(sts.seat_id, str(date_value), s)
            await db.delete(sts)

        if expired_sts:
            appt_result = await db.execute(
                select(Appointment).where(
                    and_(
                        Appointment.seat_id.in_([sts.seat_id for sts in expired_sts]),
                        Appointment.date == date_value,
                        Appointment.slot == TimeSlot(s),
                        Appointment.status == AppointmentStatus.booked,
                    )
                )
            )
            for appt in appt_result.scalars().all():
                appt.status = AppointmentStatus.expired

        cleaned += len(expired_sts)

    if cleaned:
        await db.commit()
    return cleaned
