"""图书相关 Pydantic 模型"""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field


class BookCreate(BaseModel):
    """新增图书请求"""
    title: str = Field(min_length=1, max_length=256)
    author: str = Field(min_length=1, max_length=128)
    isbn: str | None = Field(default=None, max_length=20)
    publisher: str | None = Field(default=None, max_length=128)
    publish_year: int | None = Field(default=None, ge=1000, le=2100)
    category: str | None = Field(default=None, max_length=64)
    location: str | None = Field(default=None, max_length=128)
    total: int = Field(default=1, ge=1)
    available: int = Field(default=1, ge=0)


class BookUpdate(BaseModel):
    """更新图书请求 — 所有字段可选"""
    title: str | None = Field(default=None, min_length=1, max_length=256)
    author: str | None = Field(default=None, min_length=1, max_length=128)
    isbn: str | None = Field(default=None, max_length=20)
    publisher: str | None = Field(default=None, max_length=128)
    publish_year: int | None = Field(default=None, ge=1000, le=2100)
    category: str | None = Field(default=None, max_length=64)
    location: str | None = Field(default=None, max_length=128)
    total: int | None = Field(default=None, ge=1)
    available: int | None = Field(default=None, ge=0)


class BookResponse(BaseModel):
    """图书响应"""
    id: str
    title: str
    author: str
    isbn: str | None = None
    publisher: str | None = None
    publish_year: int | None = None
    category: str | None = None
    location: str | None = None
    total: int
    available: int
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class BookListResponse(BaseModel):
    """图书分页列表响应"""
    items: list[BookResponse]
    total: int
    offset: int
    limit: int


class BookImportPayload(BaseModel):
    """批量导入 JSON 请求"""
    items: list[BookCreate]
