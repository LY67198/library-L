from __future__ import annotations

from datetime import datetime
from typing import Any

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
    # SQLAlchemy's Declarative API reserves the attribute name "metadata" on
    # ORM classes (it refers to the table MetaData). We therefore map the SQL
    # column ``"metadata"`` under the Python attribute ``book_metadata`` and
    # expose it as ``metadata`` only at the instance level via ``__getattr__``
    # / ``__setattr__``. The Pydantic schemas (``BookCreate``,
    # ``BookResponse``) and the service/repo layer all use the public name
    # ``metadata``, which works transparently.
    book_metadata: Mapped[dict] = mapped_column("metadata", JSONB, nullable=False, default=dict)
    indexed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    def __init__(self, **kwargs: Any) -> None:
        # Translate the public kwarg name ``metadata`` (used by Pydantic
        # schemas and the public API) to the mapped attribute
        # ``book_metadata`` so ``Book(metadata=...)`` does not raise.
        if "metadata" in kwargs and "book_metadata" not in kwargs:
            kwargs["book_metadata"] = kwargs.pop("metadata")
        super().__init__(**kwargs)

    def __getattribute__(self, name: str) -> Any:
        # Route instance-level ``metadata`` access to the mapped
        # ``book_metadata`` column. We use ``__getattribute__`` (not
        # ``__getattr__``) because SQLAlchemy's Declarative Base installs
        # ``metadata`` on the class as the ``MetaData`` instance, which
        # shadows any ``__getattr__`` fallback at the instance level.
        if name == "metadata":
            try:
                return super().__getattribute__("book_metadata")
            except AttributeError:
                raise AttributeError(name)
        return super().__getattribute__(name)

    def __setattr__(self, name: str, value: Any) -> None:
        # Translate ``book.metadata = ...`` to the mapped attribute so
        # updates flow through the SQLAlchemy instrumented attribute.
        if name == "metadata":
            super().__setattr__("book_metadata", value)
            return
        super().__setattr__(name, value)
