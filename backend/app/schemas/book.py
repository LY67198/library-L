"""图书模块 — 馆藏图书的请求/响应模式,包含 RAG 检索结果。"""
from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class BookBase(BaseModel):
    """图书基础字段。"""

    isbn: str | None = Field(default=None, max_length=20, description="ISBN,可空")
    title: str = Field(..., min_length=1, max_length=256, description="书名")
    author: str | None = Field(default=None, max_length=256, description="作者")
    publisher: str | None = Field(default=None, max_length=128, description="出版社")
    category: str | None = Field(default=None, max_length=32, description="分类")
    location: str | None = Field(default=None, max_length=64, description="索书号/位置")
    total_copies: int = Field(default=1, ge=1, description="馆藏总数")
    available_copies: int = Field(default=1, ge=0, description="可借数")
    metadata: dict[str, Any] = Field(default_factory=dict, description="扩展元数据")


class BookCreate(BookBase):
    """新建图书请求体。"""


class BookUpdate(BaseModel):
    """更新图书请求体(全字段可空,部分更新)。"""

    title: str | None = Field(default=None, description="书名")
    author: str | None = Field(default=None, description="作者")
    publisher: str | None = Field(default=None, description="出版社")
    category: str | None = Field(default=None, description="分类")
    location: str | None = Field(default=None, description="索书号/位置")
    total_copies: int | None = Field(default=None, ge=1, description="馆藏总数")
    available_copies: int | None = Field(default=None, ge=0, description="可借数")
    metadata: dict[str, Any] | None = Field(default=None, description="扩展元数据")


class BookResponse(BookBase):
    """图书详情响应。"""

    id: int = Field(..., description="图书 ID")
    status: str = Field(..., description="状态(active/archived)")
    created_at: datetime = Field(..., description="创建时间")
    updated_at: datetime = Field(..., description="更新时间")


class BookSearchHit(BaseModel):
    """单条 RAG 检索命中结果。"""

    book: BookResponse = Field(..., description="命中的图书")
    score: float = Field(..., description="相关度分数")
    snippet: str | None = Field(default=None, description="摘要片段")
