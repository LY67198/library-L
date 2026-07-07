"""座位时段占用模型 — 核心并发表"""

from __future__ import annotations

import enum
from datetime import datetime

from sqlalchemy import Date, DateTime, Enum, ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import Base, new_uuid, utcnow


class TimeSlot(str, enum.Enum):
    morning = "morning"
    afternoon = "afternoon"
    evening = "evening"


class SeatTimeSlot(Base):
    __tablename__ = "seat_time_slots"
    __table_args__ = (
        UniqueConstraint("seat_id", "date", "slot", name="uq_seat_date_slot"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_uuid)
    seat_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("seats.id"), nullable=False, index=True
    )
    date: Mapped[datetime.date] = mapped_column(Date, nullable=False)
    slot: Mapped[TimeSlot] = mapped_column(
        Enum(TimeSlot, name="time_slot_enum"), nullable=False
    )
    user_id: Mapped[str] = mapped_column(String(36), ForeignKey("users.id"), nullable=False)
    booked_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    version: Mapped[int] = mapped_column(Integer, default=1, nullable=False)

    seat: Mapped["Seat"] = relationship("Seat", back_populates="time_slots")
    user: Mapped["User"] = relationship("User")
