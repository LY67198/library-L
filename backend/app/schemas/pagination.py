"""分页请求/响应模式 — 列表接口通用分页结构。"""
from __future__ import annotations

from typing import Generic, TypeVar

from pydantic import BaseModel, Field

T = TypeVar("T")


class PageRequest(BaseModel):
    """分页请求参数。"""

    page: int = Field(default=1, ge=1, description="页码,从 1 开始")
    page_size: int = Field(default=20, ge=1, le=100, description="每页条数,1-100")


class Page(BaseModel, Generic[T]):
    """通用分页响应。"""

    items: list[T] = Field(..., description="当前页数据列表")
    page: int = Field(..., description="当前页码")
    page_size: int = Field(..., description="每页条数")
    total: int = Field(..., description="总记录数")
