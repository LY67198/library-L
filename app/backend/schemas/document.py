"""文档管理 Pydantic 模型"""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field


class DocResponse(BaseModel):
    """文档响应"""
    id: str
    title: str
    filename: str
    source_type: str
    chunk_count: int
    created_at: datetime

    model_config = {"from_attributes": True}


class DocListResponse(BaseModel):
    """文档列表响应"""
    items: list[DocResponse]
    total: int
