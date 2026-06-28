"""自定义异常体系测试 — 验证 LibraryBaseError 及子类的状态码、错误码与 details 行为。"""
from app.core.exceptions import (
    Conflict,
    LibraryBaseError,
    NotFound,
    Unauthorized,
    ValidationError,
)


def test_base_error_defaults():
    """测试 LibraryBaseError 默认值:错误码为 internal_error,HTTP 状态码为 500。"""
    err = LibraryBaseError()
    assert err.code == "internal_error"
    assert err.status_code == 500


def test_unauthorized_inherits():
    """测试 Unauthorized 异常:状态码 401、错误码 unauthorized,且消息正确传递。"""
    err = Unauthorized("Token expired")
    assert err.status_code == 401
    assert err.code == "unauthorized"
    assert str(err) == "Token expired"


def test_conflict_carries_details():
    """测试 Conflict 异常:状态码 409,且 details 字典原样保留传入的上下文。"""
    err = Conflict("Seat booked", details={"seat_id": 123})
    assert err.status_code == 409
    assert err.details == {"seat_id": 123}


def test_validation_error_is_client_error():
    """测试 ValidationError 异常:状态码 422,作为客户端校验错误使用。"""
    err = ValidationError("Bad input")
    assert err.status_code == 422


def test_not_found():
    """测试 NotFound 异常:状态码 404、错误码 not_found,用于资源缺失场景。"""
    err = NotFound("Book not found")
    assert err.status_code == 404
    assert err.code == "not_found"
