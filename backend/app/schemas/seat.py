"""座位模块 — 图书馆座位信息的响应模式。"""
from __future__ import annotations

from pydantic import BaseModel, Field


class SeatResponse(BaseModel):
    """座位详情响应。"""

    id: int = Field(..., description="座位 ID")
    code: str = Field(..., description="座位编号")
    floor: str = Field(..., description="楼层")
    zone: str = Field(..., description="区域")
    status: str = Field(..., description="状态(available/booked/maintenance)")
    has_power: bool = Field(..., description="是否有电源")
    has_monitor: bool = Field(..., description="是否有显示器")
    coord_x: int = Field(..., description="布局图 X 坐标")
    coord_y: int = Field(..., description="布局图 Y 坐标")


class SeatListResponse(BaseModel):
    """座位列表响应。"""

    items: list[SeatResponse] = Field(..., description="座位列表")
    total: int = Field(..., description="总条数")
