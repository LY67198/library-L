from __future__ import annotations

from datetime import date, datetime

from pydantic import BaseModel, Field


class PolicyBase(BaseModel):
    title: str = Field(..., min_length=1, max_length=256)
    content: str = Field(..., min_length=1)
    category: str | None = Field(default=None, max_length=32)
    effective_from: date | None = None
    effective_to: date | None = None


class PolicyCreate(PolicyBase):
    pass


class PolicyUpdate(BaseModel):
    title: str | None = None
    content: str | None = None
    category: str | None = None
    effective_from: date | None = None
    effective_to: date | None = None


class PolicyResponse(PolicyBase):
    id: int
    version: int
    indexed_at: datetime | None
    created_at: datetime
    updated_at: datetime