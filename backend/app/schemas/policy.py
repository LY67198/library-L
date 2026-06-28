"""政策/规章模块 — 图书馆规章制度的请求与响应模式,供 RAG 检索。"""
from __future__ import annotations

from datetime import date, datetime

from pydantic import BaseModel, Field


class PolicyBase(BaseModel):
    """政策基础字段。"""

    title: str = Field(..., min_length=1, max_length=256, description="标题")
    content: str = Field(..., min_length=1, description="正文内容")
    category: str | None = Field(default=None, max_length=32, description="分类")
    effective_from: date | None = Field(default=None, description="生效起始日期")
    effective_to: date | None = Field(default=None, description="生效结束日期")


class PolicyCreate(PolicyBase):
    """新建政策请求体。"""


class PolicyUpdate(BaseModel):
    """更新政策请求体(全字段可空,部分更新)。"""

    title: str | None = Field(default=None, description="标题")
    content: str | None = Field(default=None, description="正文内容")
    category: str | None = Field(default=None, description="分类")
    effective_from: date | None = Field(default=None, description="生效起始日期")
    effective_to: date | None = Field(default=None, description="生效结束日期")


class PolicyResponse(PolicyBase):
    """政策详情响应。"""

    id: int = Field(..., description="政策 ID")
    version: int = Field(..., description="版本号")
    indexed_at: datetime | None = Field(..., description="最近入索引时间")
    created_at: datetime = Field(..., description="创建时间")
    updated_at: datetime = Field(..., description="更新时间")
