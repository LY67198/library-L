"""领域异常体系 — 统一错误响应模型,所有业务异常均派生于 LibraryBaseError。
"""
from __future__ import annotations

from typing import Any


class LibraryBaseError(Exception):
    """所有库领域异常的基类,提供统一的 code / status_code / message / details 字段。"""

    code: str = "internal_error"
    status_code: int = 500
    message: str = "Internal error"

    def __init__(self, message: str | None = None, *, details: dict[str, Any] | None = None):
        """构造领域异常。

        参数:
            message: 可选的自定义错误消息;为空时使用类级默认 message。
            details: 可选的附加上下文,会原样回传给客户端。
        """
        super().__init__(message or self.message)
        self.message = message or self.message
        self.details = details or {}


class ClientError(LibraryBaseError):
    """客户端请求层面的错误基类(HTTP 4xx)。"""

    status_code = 400


class Unauthorized(LibraryBaseError):
    """未登录或登录态失效(HTTP 401)。"""

    code = "unauthorized"
    status_code = 401
    message = "Authentication required"


class Forbidden(LibraryBaseError):
    """已登录但权限不足(HTTP 403)。"""

    code = "forbidden"
    status_code = 403
    message = "Permission denied"


class NotFound(LibraryBaseError):
    """目标资源不存在(HTTP 404)。"""

    code = "not_found"
    status_code = 404
    message = "Resource not found"


class Conflict(LibraryBaseError):
    """资源状态冲突(如重复创建、并发抢占)(HTTP 409)。"""

    code = "conflict"
    status_code = 409
    message = "Resource conflict"


class ValidationError(ClientError):
    """请求体 / 参数校验失败(HTTP 422)。"""

    code = "validation_error"
    status_code = 422
    message = "Request validation failed"


class RateLimited(LibraryBaseError):
    """触发限流(HTTP 429)。"""

    code = "rate_limited"
    status_code = 429
    message = "Too many requests"


class UpstreamError(LibraryBaseError):
    """上游服务调用失败的基类(HTTP 5xx)。"""

    status_code = 502


class LLMUnavailable(UpstreamError):
    """LLM 服务不可用。"""

    code = "llm_unavailable"
    message = "LLM service unavailable"


class ChromaUnavailable(UpstreamError):
    """向量存储(ChromaDB)不可用。"""

    code = "chroma_unavailable"
    message = "Vector store unavailable"