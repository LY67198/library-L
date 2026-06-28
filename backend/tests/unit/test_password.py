"""密码哈希测试 — 验证 hash_password/verify_password 的正确性、错误密码拒绝与 salt 唯一性。"""
from __future__ import annotations

from app.core.security import hash_password, verify_password


def test_hash_and_verify_password():
    """测试密码哈希与校验:明文经哈希后与原文不同,正确密码校验通过,错误密码被拒绝。"""
    plain = "my_secure_password_123"
    hashed = hash_password(plain)
    assert hashed != plain
    assert verify_password(plain, hashed) is True
    assert verify_password("wrong_password", hashed) is False


def test_hash_is_unique_per_call():
    """测试相同明文每次哈希结果不同(因 bcrypt salt),但两个哈希都能被 verify_password 校验通过。"""
    plain = "same_password"
    h1 = hash_password(plain)
    h2 = hash_password(plain)
    assert h1 != h2  # bcrypt salt
    assert verify_password(plain, h1)
    assert verify_password(plain, h2)
