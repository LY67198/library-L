from app.core.exceptions import (
    Conflict,
    LibraryBaseError,
    NotFound,
    Unauthorized,
    ValidationError,
)


def test_base_error_defaults():
    err = LibraryBaseError()
    assert err.code == "internal_error"
    assert err.status_code == 500


def test_unauthorized_inherits():
    err = Unauthorized("Token expired")
    assert err.status_code == 401
    assert err.code == "unauthorized"
    assert str(err) == "Token expired"


def test_conflict_carries_details():
    err = Conflict("Seat booked", details={"seat_id": 123})
    assert err.status_code == 409
    assert err.details == {"seat_id": 123}


def test_validation_error_is_client_error():
    err = ValidationError("Bad input")
    assert err.status_code == 422


def test_not_found():
    err = NotFound("Book not found")
    assert err.status_code == 404
    assert err.code == "not_found"
