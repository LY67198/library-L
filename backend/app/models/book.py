from __future__ import annotations

from datetime import datetime

from sqlalchemy import BigInteger, DateTime, Index, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import TenantScopedMixin
from app.models.enums import BookStatus


class Book(TenantScopedMixin):
    __tablename__ = "books"
    __table_args__ = (
        Index("idx_books_tenant_title", "tenant_id", "title"),
        Index("idx_books_tenant_author", "tenant_id", "author"),
        Index("idx_books_tenant_category", "tenant_id", "category"),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    isbn: Mapped[str | None] = mapped_column(String(20))
    title: Mapped[str] = mapped_column(String(256), nullable=False)
    author: Mapped[str | None] = mapped_column(String(256))
    publisher: Mapped[str | None] = mapped_column(String(128))
    category: Mapped[str | None] = mapped_column(String(32))
    location: Mapped[str | None] = mapped_column(String(64))
    status: Mapped[str] = mapped_column(String(16), nullable=False, default=BookStatus.available.value)
    total_copies: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    available_copies: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    book_metadata: Mapped[dict] = mapped_column("metadata", JSONB, nullable=False, default=dict)
    indexed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
