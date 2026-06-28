"""座位预约模块 — 创建/查询/取消预约的请求与响应模式。"""
from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field


class AppointmentCreate(BaseModel):
    """新建预约请求体。"""

    seat_id: int = Field(..., ge=1, description="座位 ID")
    start_time: datetime = Field(..., description="开始时间")
    end_time: datetime = Field(..., description="结束时间")


class AppointmentResponse(BaseModel):
    """预约详情响应。"""

    id: int = Field(..., description="预约 ID")
    user_id: int = Field(..., description="用户 ID")
    seat_id: int | None = Field(..., description="座位 ID")
    start_time: datetime = Field(..., description="开始时间")
    end_time: datetime = Field(..., description="结束时间")
    status: str = Field(..., description="状态(pending/active/finished/cancelled)")
    version: int = Field(..., description="乐观锁版本号")


class AppointmentCancelRequest(BaseModel):
    """取消预约请求体。"""

    reason: str | None = Field(default=None, max_length=128, description="取消原因")
