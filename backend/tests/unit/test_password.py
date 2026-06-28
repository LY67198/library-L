from app.core.security import hash_password, verify_password


def test_hash_and_verify_password():
    plain = "my_secure_password_123"
    hashed = hash_password(plain)
    assert hashed != plain
    assert verify_password(plain, hashed) is True
    assert verify_password("wrong_password", hashed) is False


def test_hash_is_unique_per_call():
    plain = "same_password"
    h1 = hash_password(plain)
    h2 = hash_password(plain)
    assert h1 != h2  # bcrypt salt
    assert verify_password(plain, h1)
    assert verify_password(plain, h2)
