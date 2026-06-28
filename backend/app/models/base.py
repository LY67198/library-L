"""ORM 基础类与混入 — 提供 DeclarativeBase、时间戳混入、多租户字段混入与可复用 Annotated 类型。"""
from __future__ import annotations

from datetime import datetime
from typing import Annotated
from uuid import UUID

from sqlalchemy import DateTime, ForeignKey, func
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    """SQLAlchemy 声明式基类,所有 ORM 模型均继承自该类。"""


class TimestampMixin(Base):
    """为模型添加 ``created_at`` 与 ``updated_at`` 时间戳字段。

    继承自 :class:`Base`,使仅使用本混入(不显式继承 ``Base``)的模型
    仍能注册到 ``Base.metadata`` 中。
    """

    __abstract__ = True

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )


class TenantScopedMixin(TimestampMixin):
    """为模型添加 ``tenant_id`` 外键字段,并为该字段建立索引以支持多租户查询。"""

    __abstract__ = True

    tenant_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("tenants.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )


# Reusable annotated types
TenantId = Annotated[UUID, mapped_column(PGUUID(as_uuid=True), ForeignKey("tenants.id"))]
CreatedAt = Annotated[datetime, mapped_column(DateTime(timezone=True), server_default=func.now())]
UpdatedAt = Annotated[
    datetime,
    mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now()),
]
