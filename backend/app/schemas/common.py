"""通用响应模式 — 统一的错误响应结构。"""
from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class ErrorDetail(BaseModel):
    """错误响应载荷。"""

    code: str = Field(..., description="错误码,机器可读")
    message: str = Field(..., description="错误描述,人类可读")
    details: dict[str, Any] = Field(default_factory=dict, description="附加上下文信息")
    trace_id: str | None = Field(default=None, description="链路追踪 ID,用于排障")
    request_id: str | None = Field(default=None, description="请求 ID,关联日志")


class ErrorResponse(BaseModel):
    """统一错误响应包装。"""

    error: ErrorDetail = Field(..., description="错误详情")
