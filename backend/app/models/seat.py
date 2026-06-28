from __future__ import annotations

from sqlalchemy import BigInteger, Boolean, Index, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import TenantScopedMixin
from app.models.enums import SeatStatus, SeatZone


class Seat(TenantScopedMixin):
    __tablename__ = "seats"
    __table_args__ = (
        UniqueConstraint("tenant_id", "code", name="uq_seats_tenant_code"),
        Index("idx_seats_tenant_floor", "tenant_id", "floor"),
        Index("idx_seats_tenant_status", "tenant_id", "status"),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    code: Mapped[str] = mapped_column(String(16), nullable=False)
    floor: Mapped[str] = mapped_column(String(8), nullable=False)
    zone: Mapped[str] = mapped_column(String(16), nullable=False, default=SeatZone.individual.value)
    status: Mapped[str] = mapped_column(String(16), nullable=False, default=SeatStatus.available.value)
    has_power: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    has_monitor: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    coord_x: Mapped[int] = mapped_column(Integer, nullable=False)
    coord_y: Mapped[int] = mapped_column(Integer, nullable=False)
