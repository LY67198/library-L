from __future__ import annotations

from datetime import datetime

from sqlalchemy import (
    BigInteger,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import TenantScopedMixin
from app.models.enums import AppointmentResource, AppointmentStatus


class Appointment(TenantScopedMixin):
    __tablename__ = "appointments"
    __table_args__ = (
        CheckConstraint("end_time > start_time", name="ck_appt_end_after_start"),
        Index(
            "idx_appt_resource_time",
            "tenant_id",
            "resource_type",
            "resource_id",
            "start_time",
            "end_time",
        ),
        Index("idx_appt_user_status", "tenant_id", "user_id", "status"),
        Index("idx_appt_status_endtime", "status", "end_time"),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("users.id"), nullable=False)
    resource_type: Mapped[str] = mapped_column(
        String(16), nullable=False, default=AppointmentResource.seat.value
    )
    resource_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    seat_id: Mapped[int | None] = mapped_column(BigInteger, ForeignKey("seats.id"))
    start_time: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    end_time: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    status: Mapped[str] = mapped_column(
        String(16), nullable=False, default=AppointmentStatus.pending.value
    )
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    confirmed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    cancelled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    cancel_reason: Mapped[str | None] = mapped_column(String(128))
