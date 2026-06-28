from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class BookBase(BaseModel):
    isbn: str | None = Field(default=None, max_length=20)
    title: str = Field(..., min_length=1, max_length=256)
    author: str | None = Field(default=None, max_length=256)
    publisher: str | None = Field(default=None, max_length=128)
    category: str | None = Field(default=None, max_length=32)
    location: str | None = Field(default=None, max_length=64)
    total_copies: int = Field(default=1, ge=1)
    available_copies: int = Field(default=1, ge=0)
    metadata: dict[str, Any] = Field(default_factory=dict)


class BookCreate(BookBase):
    pass


class BookUpdate(BaseModel):
    title: str | None = None
    author: str | None = None
    publisher: str | None = None
    category: str | None = None
    location: str | None = None
    total_copies: int | None = Field(default=None, ge=1)
    available_copies: int | None = Field(default=None, ge=0)
    metadata: dict[str, Any] | None = None


class BookResponse(BookBase):
    id: int
    status: str
    created_at: datetime
    updated_at: datetime


class BookSearchHit(BaseModel):
    """One book hit returned by RAG-augmented search."""
    book: BookResponse
    score: float
    snippet: str | None = None