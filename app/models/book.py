"""图书模型"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from .base import Base, new_uuid, utcnow


class Book(Base):
    __tablename__ = "books"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_uuid)
    title: Mapped[str] = mapped_column(String(256), nullable=False, index=True)
    author: Mapped[str] = mapped_column(String(128), nullable=False)
    isbn: Mapped[str | None] = mapped_column(String(20), unique=True, index=True, nullable=True)
    publisher: Mapped[str | None] = mapped_column(String(128), nullable=True)
    publish_year: Mapped[int | None] = mapped_column(Integer, nullable=True)
    category: Mapped[str | None] = mapped_column(String(64), index=True, nullable=True)
    location: Mapped[str | None] = mapped_column(String(128), nullable=True)
    total: Mapped[int] = mapped_column(Integer, default=1, server_default="1")
    available: Mapped[int] = mapped_column(Integer, default=1, server_default="1")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)
