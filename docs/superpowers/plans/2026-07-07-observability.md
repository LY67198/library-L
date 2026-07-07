# 可观测性 实现计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 为图书馆系统增加全链路追踪 — Trace ID 注入、结构化日志、OpenTelemetry FastAPI 自动插桩、LLM 调用日志关联、全局异常 trace_id

**Architecture:** 纯 ASGI 中间件层（TraceMiddleware）生成/传递 trace_id，ContextVar 异步安全，Logging Filter 自动注入，OTel SDK 可选开启。不修改任何现有业务代码。

**Tech Stack:** Python `contextvars`, `opentelemetry-api` + `opentelemetry-sdk` + `opentelemetry-instrumentation-fastapi`, `python-json-logger`

---

### Task 1: 添加依赖

**Files:**
- Modify: `pyproject.toml`

- [ ] **Step 1: 在 pyproject.toml 添加依赖**

在 `dependencies` 数组中追加以下行：
```toml
"opentelemetry-api>=1.35",
"opentelemetry-sdk>=1.35",
"opentelemetry-instrumentation-fastapi>=0.56",
"python-json-logger>=3.3",
```

- [ ] **Step 2: 安装依赖**

Run: `uv pip install opentelemetry-api opentelemetry-sdk opentelemetry-instrumentation-fastapi python-json-logger`
Expected: 成功安装，无错误

- [ ] **Step 3: 提交**

```bash
git add pyproject.toml uv.lock
git commit -m "feat: 添加可观测性依赖（OTel + JSON logger）"
```

---

### Task 2: AppSettings 新增配置字段

**Files:**
- Modify: `app/backend/config/settings.py`

- [ ] **Step 1: 在 AppSettings 类中新增 6 个字段**

在 `deepseek_model` 字段之后追加：

```python
# 可观测性
otel_enabled: bool = True
otel_exporter_jaeger_enabled: bool = False
otel_jaeger_agent_host: str = "localhost"
otel_jaeger_agent_port: int = 6831
log_format: str = "text"  # text | json
```

- [ ] **Step 2: 验证 Setting 加载**

Run: `.venv/Scripts/python.exe -c "from app.backend.config.settings import AppSettings; s = AppSettings(); print(s.otel_enabled, s.log_format)"`
Expected: `True text`

- [ ] **Step 3: 提交**

```bash
git add app/backend/config/settings.py
git commit -m "feat: AppSettings 新增可观测性配置字段"
```

---

### Task 3: observability 包初始化

**Files:**
- Create: `app/observability/__init__.py`

- [ ] **Step 1: 创建 __init__.py**

```python
"""可观测性模块 — trace_id 传递、结构化日志、OpenTelemetry 集成"""

from __future__ import annotations

from observability.middleware import TraceMiddleware, get_trace_id
from observability.logging import setup_logging

__all__ = ["TraceMiddleware", "get_trace_id", "setup_logging"]
```

- [ ] **Step 2: 提交**

```bash
git add app/observability/__init__.py
git commit -m "feat: 创建 observability 包初始化"
```

---

### Task 4: TraceMiddleware 实现

**Files:**
- Create: `app/observability/middleware.py`
- Create: `tests/test_observability.py`

- [ ] **Step 1: 写失败测试 — test_observability.py**

```python
"""可观测性模块测试"""
import json
import logging
import re
from unittest.mock import patch

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

        import logging
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

        import logging
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

        import logging
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
        from observability.logging import setup_logging

        logger = setup_logging(log_format="json")
        handlers = [h for h in logger.handlers if isinstance(h, logging.StreamHandler)]
        assert len(handlers) > 0
        # At least one handler has a TraceIdFilter
        handler_has_filter = any(
            isinstance(f, __import__("observability.logging", fromlist=["TraceIdFilter"]).TraceIdFilter)
            for h in handlers
            for f in h.filters
        )
        assert handler_has_filter
```

- [ ] **Step 2: 运行测试验证失败**

Run: `.venv/Scripts/python.exe -m pytest tests/test_observability.py -v`
Expected: 全部 FAIL（模块未创建）

- [ ] **Step 3: 创建 observability/middleware.py**

```python
"""纯 ASGI Trace 中间件 — UUID7 生成 + ContextVar 传递"""

from __future__ import annotations

import contextvars
import time
import uuid

_trace_id_var: contextvars.ContextVar[str | None] = contextvars.ContextVar(
    "trace_id", default=None
)

# UUID7 生成所需常量
_UUID7_EPOCH_NS = 0x01B21DD213814000  # 2020-01-01 00:00:00 in 100ns ticks


def _uuid7() -> str:
    """生成 UUID7（时间排序的 UUID）"""
    now_ns = time.time_ns()
    # 100ns ticks since UUID epoch
    ticks = now_ns // 100 + _UUID7_EPOCH_NS
    ticks_hex = f"{ticks:016x}"
    rand_hex = uuid.uuid4().hex[16:]
    combined = ticks_hex + rand_hex[:4] + "7" + rand_hex[5:]
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
```

- [ ] **Step 4: 创建 observability/logging.py**

```python
"""结构化日志 — JSON formatter + trace_id 注入"""

from __future__ import annotations

import logging
import sys
from datetime import datetime, timezone

from observability.middleware import get_trace_id


class TraceIdFilter(logging.Filter):
    """自动将 ContextVar 中的 trace_id 注入日志记录"""

    def filter(self, record: logging.LogRecord) -> bool:
        record.trace_id = get_trace_id() or "-"
        return True


class JsonFormatter(logging.Formatter):
    """JSON 格式日志输出"""

    def format(self, record: logging.LogRecord) -> str:
        import json

        log_entry = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "trace_id": getattr(record, "trace_id", "-"),
            "message": record.getMessage(),
        }
        if record.exc_info and record.exc_info[0]:
            log_entry["exception"] = self.formatException(record.exc_info)
        return json.dumps(log_entry, ensure_ascii=False)


def setup_logging(log_format: str = "text") -> logging.Logger:
    """初始化根日志配置

    Args:
        log_format: "text"（默认多行格式）或 "json"（生产用）

    Returns:
        根 logger
    """
    root = logging.getLogger()

    # 清空已有 handler（避免 basicConfig 叠加）
    if root.handlers:
        root.handlers.clear()

    handler = logging.StreamHandler(sys.stdout)

    if log_format == "json":
        formatter = JsonFormatter()
    else:
        formatter = logging.Formatter(
            "%(asctime)s | %(levelname)s | %(trace_id)s | %(name)s | %(message)s",
            datefmt="%Y-%m-%dT%H:%M:%S",
        )

    handler.setFormatter(formatter)
    handler.addFilter(TraceIdFilter())
    root.addHandler(handler)
    root.setLevel(logging.INFO)

    # 降低噪音
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("chromadb").setLevel(logging.WARNING)

    return root
```

- [ ] **Step 5: 运行测试**

Run: `.venv/Scripts/python.exe -m pytest tests/test_observability.py -v`
Expected: 8 tests passed

- [ ] **Step 6: 提交**

```bash
git add app/observability/middleware.py app/observability/logging.py tests/test_observability.py
git commit -m "feat: 实现 TraceMiddleware + 结构化日志 + 测试"
```

---

### Task 5: app_main.py 集成

**Files:**
- Modify: `app/app_main.py`
- Modify: `tests/test_observability.py`（追加集成测试）

- [ ] **Step 1: 改造 app_main.py**

```python
from __future__ import annotations

import logging
import sys
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

APP_DIR = Path(__file__).resolve().parent
if str(APP_DIR) not in sys.path:
    sys.path.insert(0, str(APP_DIR))

from backend.config.settings import AppSettings
from backend.router.health_router import router as health_router

from backend.router.chat_router import router as chat_router
from backend.router.book_router import router as book_router
from backend.router.auth_router import router as auth_router
from backend.router.seat_router import router as seat_router
from backend.router.admin_book_router import router as admin_book_router
from backend.router.admin_doc_router import router as admin_doc_router

from mcp_server.auth import McpAuthMiddleware
from mcp_server.server import create_mcp_sse_app

from observability import TraceMiddleware, get_trace_id, setup_logging


def create_app() -> FastAPI:
    settings = AppSettings()

    # 日志初始化（必须在 logging.basicConfig 之前调用）
    setup_logging(log_format=settings.log_format)

    app = FastAPI(title=settings.app_name)

    # Trace 中间件（最外层，第一个执行）
    app.add_middleware(TraceMiddleware)

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins(),
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.add_middleware(McpAuthMiddleware)

    app.include_router(health_router)

    app.include_router(chat_router)
    app.include_router(book_router)
    app.include_router(auth_router)
    app.include_router(seat_router)
    app.include_router(admin_book_router)
    app.include_router(admin_doc_router)

    app.mount("/api/v1/mcp", create_mcp_sse_app())

    # 全局异常处理
    @app.exception_handler(Exception)
    async def global_exception_handler(request: Request, exc: Exception):
        import logging
        logger = logging.getLogger(__name__)
        logger.exception(f"未处理的异常: {exc}")
        return JSONResponse(
            status_code=500,
            content={
                "error": "internal_error",
                "trace_id": get_trace_id() or "-",
                "detail": str(exc) if settings.app_env == "development" else "服务器内部错误",
            },
        )

    # OpenTelemetry（可选）
    if settings.otel_enabled:
        _setup_otel(app, settings)

    return app


def _setup_otel(app: FastAPI, settings: AppSettings) -> None:
    """初始化 OpenTelemetry — FastAPI auto-instrumentation"""
    try:
        from opentelemetry import trace
        from opentelemetry.sdk.trace import TracerProvider
        from opentelemetry.sdk.trace.export import BatchSpanProcessor
        from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
        from opentelemetry.sdk.resources import Resource

        resource = Resource.create({"service.name": settings.app_name})
        provider = TracerProvider(resource=resource)

        if settings.otel_exporter_jaeger_enabled:
            from opentelemetry.exporter.jaeger.thrift import JaegerExporter
            jaeger_exporter = JaegerExporter(
                agent_host_name=settings.otel_jaeger_agent_host,
                agent_port=settings.otel_jaeger_agent_port,
            )
            provider.add_span_processor(BatchSpanProcessor(jaeger_exporter))

        trace.set_tracer_provider(provider)
        FastAPIInstrumentor.instrument_app(app)
        logging.getLogger(__name__).info("OpenTelemetry initialized")
    except Exception:
        logging.getLogger(__name__).warning(
            "OpenTelemetry 初始化失败，跳过", exc_info=True
        )


app = create_app()


if __name__ == "__main__":
    import uvicorn

    runtime_settings = AppSettings()
    uvicorn.run(
        "app_main:app",
        host=runtime_settings.host,
        port=runtime_settings.port,
        reload=runtime_settings.app_env == "development",
    )
```

- [ ] **Step 2: 追加集成测试到 test_observability.py**

```python
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
        # 请求不存在的路由，触发 404（FastAPI 内部处理，非全局异常）
        resp = client.get("/api/v1/nonexistent")
        # 404 也应该有 X-Trace-Id
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
```

- [ ] **Step 3: 运行测试**

Run: `.venv/Scripts/python.exe -m pytest tests/test_observability.py -v`
Expected: 11 tests passed（8 单元 + 3 集成）

- [ ] **Step 4: 运行全量测试确保无回归**

Run: `.venv/Scripts/python.exe -m pytest tests/ -v`
Expected: 之前通过的测试仍通过（MCP 14 + observability 11 + 其他）

- [ ] **Step 5: 提交**

```bash
git add app/app_main.py tests/test_observability.py
git commit -m "feat: app_main 集成 TraceMiddleware + 全局异常 trace_id + OTel 可选"
```

---

### Task 6: LLM 调用日志关联 trace_id

**Files:**
- Modify: `app/agents/llm_client/client.py`

- [ ] **Step 1: 在 _call_with_fallback 日志中注入 trace_id**

修改 `app/agents/llm_client/client.py`，在文件开头导入 `get_trace_id`：

```python
from observability.middleware import get_trace_id
```

然后修改 `_call_with_fallback` 函数内部的日志记录，在 `logger.warning` 后增加一条 `logger.info`：

在 `_call_with_fallback` 函数中的 `for client, model in ...:` 循环内，成功返回前增加：

```python
import time as _time
```

替换整个 `_call_with_fallback` 函数为：

```python
def _call_with_fallback(
    *,
    primary: Any,
    primary_model: str,
    secondary: Any,
    secondary_model: str,
    system_prompt: str,
    user_message: str,
    parser: Callable[[str], T],
    temperature: float = 0.1,
    max_tokens: int = 1024,
) -> T:
    """MiniMax → DeepSeek → raise RuntimeError"""
    for client, model in [(primary, primary_model), (secondary, secondary_model)]:
        try:
            start = _time.monotonic()
            resp = client.chat.completions.create(
                model=model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_message},
                ],
                temperature=temperature,
                max_tokens=max_tokens,
            )
            latency_ms = int((_time.monotonic() - start) * 1000)
            raw = resp.choices[0].message.content
            result = parser(raw)
            logger.info(
                "LLM call completed: model=%s, latency_ms=%d, trace_id=%s",
                model, latency_ms, get_trace_id() or "-",
            )
            return result
        except Exception as exc:
            logger.warning(
                "LLM call failed: model=%s, error=%s, trace_id=%s",
                model, exc, get_trace_id() or "-",
            )

    raise RuntimeError("All LLM backends failed")
```

- [ ] **Step 2: 运行 LLM 相关测试**

Run: `.venv/Scripts/python.exe -m pytest tests/test_real_llm_client.py tests/test_intent_classification.py tests/test_library_graph.py -v`
Expected: 通过（LLM 测试不依赖真实 API Key）

- [ ] **Step 3: 提交**

```bash
git add app/agents/llm_client/client.py
git commit -m "feat: LLM 调用日志关联 trace_id"
```

---

### Task 7: 更新 .env.example

**Files:**
- Modify: `.env.example`

- [ ] **Step 1: 在 .env.example 末尾追加可观测性配置**

```ini
# === 可观测性 ===
OTEL_ENABLED=true
OTEL_EXPORTER_JAEGER_ENABLED=false
OTEL_JAEGER_AGENT_HOST=localhost
OTEL_JAEGER_AGENT_PORT=6831
LOG_FORMAT=text
```

- [ ] **Step 2: 提交**

```bash
git add .env.example
git commit -m "chore: .env.example 新增可观测性配置"
```

---

### Task 8: 最终验证

- [ ] **Step 1: 运行全量测试**

Run: `.venv/Scripts/python.exe -m pytest tests/ -v --ignore=tests/test_admin_book_api.py --ignore=tests/test_admin_doc_api.py --ignore=tests/test_auth_api.py --ignore=tests/test_chat_api.py --ignore=tests/test_seat_api.py`
Expected: 所有非 DB 测试通过

- [ ] **Step 2: 启动服务验证**

Run: `.venv/Scripts/python.exe -m uvicorn app.app_main:app --port 8000 &`
Then: `curl -sI http://localhost:8000/api/v1/health | grep -i x-trace-id`
Expected: `x-trace-id: xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx`

- [ ] **Step 3: 停止服务**

Run: `kill %1` (或 Ctrl+C)

- [ ] **Step 4: 最终提交（如有修改）**

```bash
git status
# 如有未提交的修改：
git add -A
git commit -m "chore: 可观测性最终验证通过"
```
