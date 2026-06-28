from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field


class AppointmentCreate(BaseModel):
    seat_id: int = Field(..., ge=1)
    start_time: datetime
    end_time: datetime


class AppointmentResponse(BaseModel):
    id: int
    user_id: int
    seat_id: int | None
    start_time: datetime
    end_time: datetime
    status: str
    version: int


class AppointmentCancelRequest(BaseModel):
    reason: str | None = Field(default=None, max_length=128)