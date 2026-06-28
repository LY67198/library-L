from __future__ import annotations

from datetime import datetime

from sqlalchemy import BigInteger, DateTime, ForeignKey, Index, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

"""用户模型 — 租户内的系统使用者(学生/教职工/馆员/管理员)。"""

from app.models.base import TenantScopedMixin
from app.models.enums import UserRole, UserStatus


class User(TenantScopedMixin):
    """用户实体:隶属于某个租户,带有角色与状态;学号在租户内唯一。"""

    __tablename__ = "users"
    __table_args__ = (
        UniqueConstraint("tenant_id", "student_no", name="uq_users_tenant_student_no"),
        Index("idx_users_tenant_role", "tenant_id", "role"),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    student_no: Mapped[str] = mapped_column(String(32), nullable=False)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    full_name: Mapped[str] = mapped_column(String(64), nullable=False)
    email: Mapped[str | None] = mapped_column(String(128))
    role: Mapped[str] = mapped_column(String(16), nullable=False, default=UserRole.student.value)
    status: Mapped[str] = mapped_column(String(16), nullable=False, default=UserStatus.active.value)
    last_login_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
