"""预约记录模型 — 操作流水"""

from __future__ import annotations

import enum
from datetime import datetime

from sqlalchemy import Date, DateTime, Enum, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import Base, new_uuid, utcnow
from .seat_time_slot import TimeSlot


class AppointmentStatus(str, enum.Enum):
    booked = "booked"
    checked_in = "checked_in"
    cancelled = "cancelled"
    expired = "expired"


class Appointment(Base):
    __tablename__ = "appointments"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_uuid)
    user_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("users.id"), nullable=False, index=True
    )
    seat_id: Mapped[str] = mapped_column(String(36), ForeignKey("seats.id"), nullable=False)
    date: Mapped[datetime.date] = mapped_column(Date, nullable=False)
    slot: Mapped[TimeSlot] = mapped_column(
        Enum(TimeSlot, name="appointment_slot_enum"), nullable=False
    )
    status: Mapped[AppointmentStatus] = mapped_column(
        Enum(AppointmentStatus, name="appointment_status_enum"),
        default=AppointmentStatus.booked,
        nullable=False,
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, onupdate=utcnow
    )

    user: Mapped["User"] = relationship("User")
    seat: Mapped["Seat"] = relationship("Seat", back_populates="appointments")
