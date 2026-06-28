from __future__ import annotations

from typing import Any


class LibraryBaseError(Exception):
    """Base for all library domain errors."""

    code: str = "internal_error"
    status_code: int = 500
    message: str = "Internal error"

    def __init__(self, message: str | None = None, *, details: dict[str, Any] | None = None):
        super().__init__(message or self.message)
        self.message = message or self.message
        self.details = details or {}


class ClientError(LibraryBaseError):
    status_code = 400


class Unauthorized(LibraryBaseError):
    code = "unauthorized"
    status_code = 401
    message = "Authentication required"


class Forbidden(LibraryBaseError):
    code = "forbidden"
    status_code = 403
    message = "Permission denied"


class NotFound(LibraryBaseError):
    code = "not_found"
    status_code = 404
    message = "Resource not found"


class Conflict(LibraryBaseError):
    code = "conflict"
    status_code = 409
    message = "Resource conflict"


class ValidationError(ClientError):
    code = "validation_error"
    status_code = 422
    message = "Request validation failed"


class RateLimited(LibraryBaseError):
    code = "rate_limited"
    status_code = 429
    message = "Too many requests"


class UpstreamError(LibraryBaseError):
    status_code = 502


class LLMUnavailable(UpstreamError):
    code = "llm_unavailable"
    message = "LLM service unavailable"


class ChromaUnavailable(UpstreamError):
    code = "chroma_unavailable"
    message = "Vector store unavailable"
