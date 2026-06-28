"""政策模型 — 租户内的图书馆政策/规章条目,支持分类、生效期与版本。"""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import BigInteger, Date, DateTime, Index, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import TenantScopedMixin


class Policy(TenantScopedMixin):
    """政策实体:隶属于某个租户,记录规章标题/正文/分类/生效期与版本号。"""

    __tablename__ = "policies"
    __table_args__ = (Index("idx_policies_tenant_category", "tenant_id", "category"),)

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    title: Mapped[str] = mapped_column(String(256), nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    category: Mapped[str | None] = mapped_column(String(32))
    effective_from: Mapped[datetime | None] = mapped_column(Date)
    effective_to: Mapped[datetime | None] = mapped_column(Date)
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    indexed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
