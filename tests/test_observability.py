"""可观测性模块测试"""
import json
import logging
import re

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from observability.middleware import TraceMiddleware, get_trace_id, _trace_id_var


class TestTraceMiddleware:
    """X-Trace-Id 注入 & ContextVar"""

    def test_generates_trace_id_when_missing(self):
        app = FastAPI()
        app.add_middleware(TraceMiddleware)

        @app.get("/test")
        async def endpoint():
            return {"trace_id": get_trace_id()}

        client = TestClient(app)
        resp = client.get("/test")
        assert resp.status_code == 200
        assert "X-Trace-Id" in resp.headers
        trace_id = resp.headers["X-Trace-Id"]
        # UUID7 格式: 36 chars, dashes
        assert re.match(r"^[0-9a-f]{8}-[0-9a-f]{4}-7[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$", trace_id)
        assert resp.json()["trace_id"] == trace_id

    def test_reuses_incoming_trace_id(self):
        app = FastAPI()
        app.add_middleware(TraceMiddleware)

        @app.get("/test")
        async def endpoint():
            return {"trace_id": get_trace_id()}

        client = TestClient(app)
        incoming = "aaaaaaaa-bbbb-4ccc-8ddd-eeeeeeeeeeee"
        resp = client.get("/test", headers={"X-Trace-Id": incoming})
        assert resp.headers["X-Trace-Id"] == incoming
        assert resp.json()["trace_id"] == incoming

    def test_sse_stream_not_broken(self):
        """纯 ASGI 中间件不劫持 SSE 流"""
        import asyncio

        app = FastAPI()
        app.add_middleware(TraceMiddleware)

        @app.get("/stream")
        async def stream():
            from starlette.responses import StreamingResponse

            async def generate():
                for i in range(3):
                    yield f"data: chunk {i}\n\n"
                    await asyncio.sleep(0)

            return StreamingResponse(generate(), media_type="text/event-stream")

        client = TestClient(app)
        resp = client.get("/stream")
        assert resp.status_code == 200
        assert "X-Trace-Id" in resp.headers
        assert resp.text.count("data:") == 3

    def test_trace_id_var_is_none_when_not_set(self):
        """没有经过中间件时 get_trace_id 返回 None"""
        _trace_id_var.set(None)
        assert get_trace_id() is None


class TestTraceIdFilter:
    """TraceIdFilter 日志注入"""

    def test_injects_trace_id_into_log_record(self):
        from observability.logging import TraceIdFilter

        _trace_id_var.set("test-trace-123")
        log_filter = TraceIdFilter()
        record = logging.LogRecord(
            name="test", level=20, pathname=__file__, lineno=1,
            msg="hello", args=(), exc_info=None,
        )
        assert log_filter.filter(record)
        assert record.trace_id == "test-trace-123"

    def test_fallback_when_trace_id_not_set(self):
        from observability.logging import TraceIdFilter

        _trace_id_var.set(None)
        log_filter = TraceIdFilter()
        record = logging.LogRecord(
            name="test", level=20, pathname=__file__, lineno=1,
            msg="hello", args=(), exc_info=None,
        )
        assert log_filter.filter(record)
        assert record.trace_id == "-"


class TestJsonFormatter:
    """JSON 格式日志输出"""

    def test_formats_as_json_with_trace_id(self):
        from observability.logging import JsonFormatter

        _trace_id_var.set("test-trace-456")
        formatter = JsonFormatter()
        record = logging.LogRecord(
            name="test.logger", level=30, pathname=__file__, lineno=42,
            msg="something happened", args=(), exc_info=None,
        )
        record.trace_id = "test-trace-456"
        output = formatter.format(record)
        data = json.loads(output)
        assert data["level"] == "WARNING"
        assert data["logger"] == "test.logger"
        assert data["trace_id"] == "test-trace-456"
        assert data["message"] == "something happened"
        assert "timestamp" in data


class TestSetupLogging:
    """日志初始化"""

    def test_json_mode_sets_json_formatter(self):
        from observability.logging import setup_logging, TraceIdFilter

        logger = setup_logging(log_format="json")
        handlers = [h for h in logger.handlers if isinstance(h, logging.StreamHandler)]
        assert len(handlers) > 0
        # At least one handler has a TraceIdFilter
        handler_has_filter = any(
            isinstance(f, TraceIdFilter)
            for h in handlers
            for f in h.filters
        )
        assert handler_has_filter

    def test_double_initialization_does_not_accumulate_handlers(self):
        """两次调用 setup_logging 不会导致 handler 累积"""
        from observability.logging import setup_logging, JsonFormatter

        setup_logging(log_format="text")
        setup_logging(log_format="json")
        root = logging.getLogger()
        stream_handlers = [h for h in root.handlers if isinstance(h, logging.StreamHandler)]
        assert len(stream_handlers) == 1
        assert isinstance(stream_handlers[0].formatter, JsonFormatter)


class TestAppIntegration:
    """app_main 集成 — 请求级 X-Trace-Id 验证"""

    def test_every_response_has_trace_id(self):
        from app.app_main import app

        client = TestClient(app)
        resp = client.get("/api/v1/health")
        assert resp.status_code == 200
        assert "X-Trace-Id" in resp.headers

    def test_error_response_has_trace_id(self):
        from app.app_main import app

        client = TestClient(app)
        resp = client.get("/api/v1/nonexistent")
        assert "X-Trace-Id" in resp.headers

    def test_cors_headers_coexist_with_trace_id(self):
        from app.app_main import app

        client = TestClient(app)
        resp = client.options(
            "/api/v1/health",
            headers={
                "Origin": "http://localhost:5173",
                "Access-Control-Request-Method": "GET",
            },
        )
        assert "X-Trace-Id" in resp.headers
