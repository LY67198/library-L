"""鉴权模块 — 注册/登录/Token 刷新相关的请求与响应模式。"""
from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, EmailStr, Field


class RegisterRequest(BaseModel):
    """用户注册请求体。"""

    student_no: str = Field(..., min_length=4, max_length=32, description="学号,4-32 位")
    password: str = Field(..., min_length=8, max_length=128, description="密码,8-128 位")
    full_name: str = Field(..., min_length=1, max_length=64, description="姓名")
    email: EmailStr | None = Field(default=None, description="邮箱地址,可空")


class LoginRequest(BaseModel):
    """用户登录请求体。"""

    student_no: str = Field(..., min_length=1, description="学号")
    password: str = Field(..., min_length=1, description="密码")


class RefreshRequest(BaseModel):
    """刷新 Token 请求体。"""

    refresh_token: str = Field(..., description="刷新令牌")


class UserInfo(BaseModel):
    """用户信息响应。"""

    id: int = Field(..., description="用户 ID")
    student_no: str = Field(..., description="学号")
    full_name: str = Field(..., description="姓名")
    email: str | None = Field(..., description="邮箱")
    role: str = Field(..., description="角色")
    tenant_id: str = Field(..., description="租户 ID")


class TokenResponse(BaseModel):
    """登录成功响应(双 Token)。"""

    access_token: str = Field(..., description="访问令牌")
    refresh_token: str = Field(..., description="刷新令牌")
    token_type: Literal["bearer"] = Field(default="bearer", description="令牌类型")
    expires_in: int = Field(..., description="访问令牌有效期(秒)")
    user: UserInfo = Field(..., description="当前用户信息")


class AccessTokenResponse(BaseModel):
    """刷新访问令牌响应。"""

    access_token: str = Field(..., description="新的访问令牌")
    token_type: Literal["bearer"] = Field(default="bearer", description="令牌类型")
    expires_in: int = Field(..., description="访问令牌有效期(秒)")


class CurrentUserResponse(BaseModel):
    """当前登录用户信息响应。"""

    user: UserInfo = Field(..., description="用户信息")
    tenant_id: str = Field(..., description="租户 ID")
    roles: list[str] = Field(..., description="角色列表")
