from __future__ import annotations

from uuid import UUID

from sqlalchemy import String
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

"""租户模型 — 表示一个机构/学校,作为多租户隔离的最高层实体。"""

from app.models.base import TimestampMixin
from app.models.enums import TenantStatus


class Tenant(TimestampMixin):
    """租户(机构)实体:承载一套完整的图书馆业务数据,作为多租户隔离的根。"""

    __tablename__ = "tenants"

    id: Mapped[UUID] = mapped_column(primary_key=True)
    code: Mapped[str] = mapped_column(String(32), unique=True, nullable=False)
    name: Mapped[str] = mapped_column(String(128), nullable=False)
    status: Mapped[str] = mapped_column(String(16), nullable=False, default=TenantStatus.active.value)
    config: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
