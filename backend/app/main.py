"""FastAPI 应用入口 — 应用工厂、生命周期(Lifespan)、中间件与全局异常处理器。
"""
from __future__ import annotations

from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from opentelemetry import trace

from app.api.v1.router import api_router
from app.clients.embedding_client import EmbeddingClient
from app.clients.redis_client import dispose_redis, init_redis
from app.core.config import get_settings
from app.core.database import dispose_engine, init_engine
from app.core.exceptions import LibraryBaseError
from app.core.observability import init_observability, shutdown_observability
from app.rag.bm25_index import WhooshIndexManager
from app.rag.chroma_store import ChromaStore


@asynccontextmanager
async def lifespan(app: FastAPI):
    """FastAPI 应用生命周期:启动时初始化可观测性 / DB / Redis,关闭时反向释放。

    参数:
        app: 由 ``create_app`` 构建的 FastAPI 实例。

    返回值:
        AsyncIterator[None]: 异步上下文管理器,生命周期内 yield 给应用。
    """
    init_observability()
    init_engine()
    init_redis()
    yield
    await dispose_engine()
    await dispose_redis()
    shutdown_observability()


def create_app() -> FastAPI:
    """创建并装配 FastAPI 应用实例(包含 RAG 单例、CORS、路由与异常处理器)。

    返回值:
        FastAPI: 已配置完成的应用实例。
    """
    settings = get_settings()
    app = FastAPI(title=settings.app_name, version=settings.app_version, lifespan=lifespan)
    # RAG 单例(进程内,生命周期与应用一致)
    rag_base = Path("./data/rag")
    rag_base.mkdir(parents=True, exist_ok=True)
    app.state.bm25_index = WhooshIndexManager(rag_base / "bm25")
    app.state.chroma_store = ChromaStore(rag_base / "chroma")
    app.state.embedding_client = EmbeddingClient()
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.include_router(api_router)
    _register_exception_handlers(app)
    return app


def _current_trace_id() -> str | None:
    """获取当前 OpenTelemetry span 的 Trace ID(用于错误响应中回填)。

    返回值:
        str | None: 32 位十六进制 Trace ID;若当前无录制中的 span 则为 None。
    """
    span = trace.get_current_span()
    if span.is_recording():
        return format(span.get_span_context().trace_id, "032x")
    return None


def _register_exception_handlers(app: FastAPI) -> None:
    """向 FastAPI 注册全局异常处理器,把领域异常转换为统一的 JSON 响应。

    参数:
        app: 目标 FastAPI 应用实例。
    """
    @app.exception_handler(LibraryBaseError)
    async def library_error_handler(request: Request, exc: LibraryBaseError):
        """处理 ``LibraryBaseError`` 及其子类,按异常自身的 status_code 返回 JSON。"""
        return JSONResponse(
            status_code=exc.status_code,
            content={
                "error": {
                    "code": exc.code,
                    "message": exc.message,
                    "details": exc.details,
                    "trace_id": _current_trace_id(),
                    "request_id": request.headers.get("x-request-id"),
                }
            },
        )

    @app.exception_handler(RequestValidationError)
    async def validation_handler(request: Request, exc: RequestValidationError):
        """处理 FastAPI 请求体验证错误,固定返回 422。"""
        return JSONResponse(
            status_code=422,
            content={
                "error": {
                    "code": "validation_error",
                    "message": "Request validation failed",
                    "details": {"errors": exc.errors()},
                    "trace_id": _current_trace_id(),
                    "request_id": request.headers.get("x-request-id"),
                }
            },
        )

    @app.exception_handler(Exception)
    async def unhandled_handler(request: Request, exc: Exception):
        """兜底处理器,捕获所有未处理异常并以 500 + ``internal_error`` 返回。"""
        return JSONResponse(
            status_code=500,
            content={
                "error": {
                    "code": "internal_error",
                    "message": "An internal error occurred",
                    "trace_id": _current_trace_id(),
                    "request_id": request.headers.get("x-request-id"),
                }
            },
        )


app = create_app()