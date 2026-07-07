"""纯 ASGI Trace 中间件 — UUID7 生成 + ContextVar 传递"""

from __future__ import annotations

import contextvars
import time
import uuid

_trace_id_var: contextvars.ContextVar[str | None] = contextvars.ContextVar(
    "trace_id", default=None
)

def _uuid7() -> str:
    """生成 UUID7（时间排序的 UUID）

    UUID7 布局: 48-bit 时间戳(ms) | 4-bit version(7) | 12-bit rand | 2-bit variant | 62-bit rand
    """
    # Unix 毫秒时间戳（48 bits = 12 hex chars）
    ts_ms = int(time.time() * 1000)
    ts_hex = f"{ts_ms:012x}"

    # 从 UUID4 获取随机数据（32 hex chars），其 variant 位已设置
    rand_hex = uuid.uuid4().hex

    # 拼接: ts(12) + version"7"(1) + rand[13:16](3) + rand[16:32](16) = 32 chars
    combined = ts_hex + "7" + rand_hex[13:16] + rand_hex[16:]
    return f"{combined[:8]}-{combined[8:12]}-{combined[12:16]}-{combined[16:20]}-{combined[20:32]}"


def get_trace_id() -> str | None:
    """获取当前请求的 trace_id。在中间件外调用返回 None。"""
    return _trace_id_var.get()


class TraceMiddleware:
    """纯 ASGI 中间件 — 为每个 HTTP 请求注入 X-Trace-Id

    与 BaseHTTPMiddleware 不同，纯 ASGI 不会劫持响应体，
    因此兼容 SSE 流式传输。
    """

    def __init__(self, app):
        self._app = app

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            await self._app(scope, receive, send)
            return

        # 提取或生成 trace_id
        headers = {}
        for key, value in scope.get("headers", []):
            headers[key.decode("latin-1").lower()] = value.decode("latin-1")

        trace_id = headers.get("x-trace-id")
        if trace_id is None:
            trace_id = _uuid7()

        # 设置 ContextVar
        token = _trace_id_var.set(trace_id)

        # 注入响应头
        async def _send(message):
            if message["type"] == "http.response.start":
                headers_list = list(message.get("headers", []))
                headers_list.append(
                    (b"x-trace-id", trace_id.encode("latin-1"))
                )
                message["headers"] = headers_list
            await send(message)

        try:
            await self._app(scope, receive, _send)
        finally:
            _trace_id_var.reset(token)
