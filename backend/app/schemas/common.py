from __future__ import annotations

from typing import Any

from pydantic import BaseModel


class ErrorDetail(BaseModel):
    code: str
    message: str
    details: dict[str, Any] = {}
    trace_id: str | None = None
    request_id: str | None = None


class ErrorResponse(BaseModel):
    error: ErrorDetail
