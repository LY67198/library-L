"""座位模型"""

from __future__ import annotations

import enum

from sqlalchemy import Enum, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import Base, new_uuid


class SeatStatus(str, enum.Enum):
    available = "available"
    disabled = "disabled"


class Seat(Base):
    __tablename__ = "seats"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_uuid)
    zone_id: Mapped[int] = mapped_column(Integer, ForeignKey("zones.id"), nullable=False)
    seat_number: Mapped[str] = mapped_column(String(16), nullable=False)
    status: Mapped[SeatStatus] = mapped_column(
        Enum(SeatStatus, name="seat_status_enum"), default=SeatStatus.available, nullable=False
    )

    zone: Mapped["Zone"] = relationship("Zone", back_populates="seats")
    time_slots: Mapped[list["SeatTimeSlot"]] = relationship(
        "SeatTimeSlot", back_populates="seat", lazy="selectin"
    )
    appointments: Mapped[list["Appointment"]] = relationship(
        "Appointment", back_populates="seat", lazy="selectin"
    )
