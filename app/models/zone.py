"""区域模型"""

from __future__ import annotations

import enum

from sqlalchemy import Enum, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import Base


class ZoneType(str, enum.Enum):
    open = "open"
    room = "room"
    electronic = "electronic"


class Zone(Base):
    __tablename__ = "zones"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    floor_id: Mapped[int] = mapped_column(Integer, ForeignKey("floors.id"), nullable=False)
    name: Mapped[str] = mapped_column(String(32), nullable=False)
    zone_type: Mapped[ZoneType] = mapped_column(
        Enum(ZoneType, name="zone_type_enum"), default=ZoneType.open, nullable=False
    )
    sort_order: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    floor: Mapped["Floor"] = relationship("Floor", back_populates="zones")
    seats: Mapped[list["Seat"]] = relationship("Seat", back_populates="zone", lazy="selectin")
