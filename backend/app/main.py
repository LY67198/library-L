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
    init_observability()
    init_engine()
    init_redis()
    yield
    await dispose_engine()
    await dispose_redis()
    shutdown_observability()


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(title=settings.app_name, version=settings.app_version, lifespan=lifespan)
    # RAG singletons (per-process; lifetime tied to app)
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
    span = trace.get_current_span()
    if span.is_recording():
        return format(span.get_span_context().trace_id, "032x")
    return None


def _register_exception_handlers(app: FastAPI) -> None:
    @app.exception_handler(LibraryBaseError)
    async def library_error_handler(request: Request, exc: LibraryBaseError):
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
