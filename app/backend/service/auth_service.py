"""认证业务逻辑"""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from core.security import (
    create_access_token,
    create_refresh_token,
    decode_token,
    hash_password,
    verify_password,
)
from models import User


class AuthService:

    def __init__(self, db: AsyncSession):
        self._db = db

    async def register(
        self, username: str, password: str, display_name: str, student_id: str
    ) -> User:
        """注册新用户。username 或 student_id 重复时抛出 ValueError。"""
        result = await self._db.execute(select(User).where(User.username == username))
        if result.scalar_one_or_none():
            raise ValueError("用户名已存在")

        result = await self._db.execute(select(User).where(User.student_id == student_id))
        if result.scalar_one_or_none():
            raise ValueError("学号已存在")

        user = User(
            username=username,
            password_hash=hash_password(password),
            display_name=display_name,
            student_id=student_id,
        )
        self._db.add(user)
        await self._db.commit()
        await self._db.refresh(user)
        return user

    async def login(self, username: str, password: str) -> dict:
        """登录 — 返回 access_token + refresh_token"""
        result = await self._db.execute(select(User).where(User.username == username))
        user = result.scalar_one_or_none()
        if user is None or not verify_password(password, user.password_hash):
            raise ValueError("用户名或密码错误")
        if not user.is_active:
            raise ValueError("账号已被禁用")

        return {
            "access_token": create_access_token(user),
            "refresh_token": create_refresh_token(user),
            "token_type": "bearer",
        }

    async def refresh(self, refresh_token: str) -> str:
        """用 refresh_token 换取新的 access_token"""
        try:
            payload = decode_token(refresh_token)
            if payload.get("type") != "refresh":
                raise ValueError("invalid_token")
            user_id = payload.get("sub")
            if not user_id:
                raise ValueError("invalid_token")
        except ValueError:
            raise ValueError("invalid_token")

        result = await self._db.execute(select(User).where(User.id == user_id))
        user = result.scalar_one_or_none()
        if user is None or not user.is_active:
            raise ValueError("invalid_token")

        return create_access_token(user)

    async def get_user(self, user_id: str) -> User | None:
        result = await self._db.execute(select(User).where(User.id == user_id))
        return result.scalar_one_or_none()
