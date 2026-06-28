from __future__ import annotations

from pydantic import BaseModel


class SeatResponse(BaseModel):
    id: int
    code: str
    floor: str
    zone: str
    status: str
    has_power: bool
    has_monitor: bool
    coord_x: int
    coord_y: int


class SeatListResponse(BaseModel):
    items: list[SeatResponse]
    total: int