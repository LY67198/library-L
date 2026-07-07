"""文档追踪模型 — 仅存元数据，完整文本在 ChromaDB"""

from __future__ import annotations

import enum
from datetime import datetime

from sqlalchemy import DateTime, Enum, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from .base import Base, new_uuid, utcnow


class DocSourceType(str, enum.Enum):
    policy = "policy"
    rule = "rule"
    faq = "faq"
    other = "other"


class Document(Base):
    __tablename__ = "documents"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_uuid)
    title: Mapped[str] = mapped_column(String(256), nullable=False)
    filename: Mapped[str] = mapped_column(String(256), nullable=False)
    source_type: Mapped[DocSourceType] = mapped_column(
        Enum(DocSourceType, name="doc_source_type_enum"), nullable=False
    )
    chunk_count: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
