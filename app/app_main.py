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

    # 日志初始化（必须在其他模块初始化前调用）
    setup_logging(log_format=settings.log_format)

    app = FastAPI(title=settings.app_name)

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins(),
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.add_middleware(McpAuthMiddleware)

    # Trace 中间件（最外层 — 最后添加，使其包裹所有其他中间件）
    app.add_middleware(TraceMiddleware)

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
