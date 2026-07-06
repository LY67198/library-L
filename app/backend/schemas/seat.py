"""座位相关 Pydantic 模型"""

from __future__ import annotations

from pydantic import BaseModel, Field


class BookRequest(BaseModel):
    date: str = Field(description="日期 YYYY-MM-DD")
    slot: str = Field(pattern="^(morning|afternoon|evening)$")


class BookResponse(BaseModel):
    appointment_id: str
    seat_id: str
    floor_name: str
    zone_name: str
    seat_number: str
    date: str
    slot: str


class SeatItem(BaseModel):
    seat_id: str
    floor_name: str
    zone_name: str
    seat_number: str
    status: str  # available / booked / disabled
    booked_by_me: bool


class SeatListResponse(BaseModel):
    seats: list[SeatItem]


class AppointmentItem(BaseModel):
    appointment_id: str
    seat_id: str
    floor_name: str
    zone_name: str
    seat_number: str
    date: str
    slot: str
    status: str


class AppointmentListResponse(BaseModel):
    appointments: list[AppointmentItem]


class CancelResponse(BaseModel):
    appointment_id: str
    status: str  # cancelled
