# Library Service Plan 02 — Business Services + RAG Pipeline Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build business service layer (Books / Seats / Appointments / Policies) with Redis-backed concurrency, plus the full RAG pipeline (BM25 + ChromaDB dense + RRF + Rerank) for policy question answering. After this plan completes, `GET /api/v1/books?q=...&use_rag=true` returns RAG-augmented answers and `POST /api/v1/seats/book` enforces two-layer concurrency (Redis lock + PG version).

**Architecture:** Four-layer expansion of Plan 01's foundation. New `app/clients/` for external service wrappers (Redis, Embedding, Rerank, LLM-stub). New `app/rag/` package with pure-Python BM25/ChromaDB/RRF and a `HybridRetriever` orchestrator. New `app/repositories/` for book/seat/appointment/policy CRUD with mandatory `tenant_id` filter. New `app/services/` for business logic — appointment booking uses Redis distributed lock + PG `version` optimistic locking.

**Tech Stack:**
- Redis 7 (asyncio via `redis>=5.0`) for distributed locks + RAG cache
- ChromaDB 1.x (persistent client, per-tenant collections)
- Whoosh 2.7 + jieba 0.42 (BM25, per-tenant indexes)
- DashScope OpenAI-compatible API (Qwen text-embedding-v2)
- DashScope native SDK (Qwen qwen3-rerank)
- pypdf + python-docx for document loaders
- httpx for all external HTTP

**Reference Spec:** `docs/superpowers/specs/2026-06-28-library-intelligent-service-design.md` (§3 Schema, §5 RAG, §6 Concurrency, §9 API)

**Working Directory:** All work happens in `D:\Agent-Project\deep_research_scaffold\backend\`.

---

## File Structure (new this plan)

```
backend/
├── app/
│   ├── clients/                          # NEW
│   │   ├── __init__.py
│   │   ├── redis_client.py               # Redis async wrapper + init/dispose
│   │   ├── embedding_client.py           # Qwen text-embedding-v2
│   │   └── rerank_client.py              # Qwen qwen3-rerank
│   ├── core/
│   │   ├── concurrency.py                # NEW: DistributedLock + retry helper
│   │   └── retry.py                      # NEW: async retry with backoff
│   ├── rag/                              # NEW
│   │   ├── __init__.py
│   │   ├── loaders.py                    # PDF/DOCX/TXT/MD loaders
│   │   ├── chunker.py                    # Sliding-window chunker
│   │   ├── bm25_index.py                 # Whoosh index per tenant
│   │   ├── bm25_retriever.py             # BM25Retriever
│   │   ├── chroma_store.py               # ChromaDB client wrapper
│   │   ├── dense_retriever.py            # DenseRetriever
│   │   ├── rrf.py                        # Reciprocal Rank Fusion
│   │   ├── rerank.py                     # Reranker wrapper
│   │   ├── pipeline.py                   # HybridRetriever (orchestrator)
│   │   └── cache.py                      # RAG cache (LRU + Redis)
│   ├── repositories/                     # EXPAND
│   │   ├── book_repository.py            # NEW
│   │   ├── seat_repository.py            # NEW
│   │   ├── appointment_repository.py     # NEW
│   │   └── policy_repository.py          # NEW
│   ├── services/                         # EXPAND
│   │   ├── book_service.py               # NEW
│   │   ├── seat_service.py               # NEW
│   │   ├── appointment_service.py        # NEW (Redis lock + PG version)
│   │   └── policy_service.py             # NEW (with RAG indexing)
│   ├── schemas/                          # EXPAND
│   │   ├── pagination.py                 # NEW
│   │   ├── book.py                       # NEW
│   │   ├── seat.py                       # NEW
│   │   ├── appointment.py                # NEW
│   │   └── policy.py                     # NEW
│   └── api/v1/                           # EXPAND
│       ├── books.py                      # NEW
│       ├── seats.py                      # NEW
│       ├── appointments.py               # NEW
│       └── admin_policies.py             # NEW
└── tests/
    ├── unit/
    │   ├── test_chunker.py
    │   ├── test_rrf.py
    │   ├── test_concurrency.py
    │   ├── test_retry.py
    │   └── test_loaders.py
    └── integration/
        ├── test_books_api.py
        ├── test_seats_api.py
        ├── test_appointments_api.py
        └── test_policies_api.py
```

---

## Phase 1: Redis Client + Distributed Lock

### Task 1: Redis async client wrapper

**Files:**
- Create: `backend/app/clients/__init__.py`
- Create: `backend/app/clients/redis_client.py`

- [ ] **Step 1: Create clients package**

```bash
mkdir -p backend/app/clients && touch backend/app/clients/__init__.py
```

- [ ] **Step 2: Add `redis>=5.0` dependency**

```bash
cd backend && uv add "redis>=5.0.0"
```

- [ ] **Step 3: Write `redis_client.py`**

Create `backend/app/clients/redis_client.py`:

```python
"""Async Redis client wrapper."""
from __future__ import annotations

from redis.asyncio import Redis, from_url

from app.core.config import get_settings

_redis: Redis | None = None


def init_redis() -> Redis:
    """Initialize global Redis client. Called from app lifespan."""
    global _redis
    if _redis is not None:
        return _redis
    settings = get_settings()
    _redis = from_url(
        settings.redis_url,
        encoding="utf-8",
        decode_responses=True,
        socket_connect_timeout=2.0,
        socket_timeout=2.0,
    )
    return _redis


async def dispose_redis() -> None:
    global _redis
    if _redis is not None:
        await _redis.aclose()
    _redis = None


def get_redis() -> Redis:
    if _redis is None:
        init_redis()
    assert _redis is not None
    return _redis
```

- [ ] **Step 4: Verify imports**

```bash
cd backend && uv run python -c "from app.clients.redis_client import init_redis, get_redis, dispose_redis; print('OK')"
```
Expected: `OK`

- [ ] **Step 5: Commit**

```bash
git add backend/app/clients/redis_client.py backend/pyproject.toml backend/uv.lock
git commit -m "feat(clients): async Redis client wrapper (init/dispose/get)"
```

---

### Task 2: Distributed lock

**Files:**
- Create: `backend/app/core/concurrency.py`
- Create: `backend/tests/unit/test_concurrency.py`

- [ ] **Step 1: Write the failing test**

Create `backend/tests/unit/test_concurrency.py`:

```python
"""DistributedLock tests use fakeredis to avoid real Redis dependency."""
import asyncio
import pytest

from app.core.concurrency import LockAcquireError, DistributedLock


class FakeRedis:
    """Minimal Redis stub: SET NX PX, EVAL, GET, DELETE."""

    def __init__(self):
        self.store: dict[str, tuple[str, int]] = {}  # key -> (value, expire_ms)
        self.now_ms = 1_000_000

    async def set(self, key, value, nx=False, px=None):
        if nx and key in self.store:
            return None
        self.store[key] = (value, self.now_ms + (px or 0))
        return "OK"

    async def get(self, key):
        v = self.store.get(key)
        if v is None:
            return None
        if v[1] and v[1] < self.now_ms:
            del self.store[key]
            return None
        return v[0]

    async def eval(self, script, numkeys, key, token):
        # Release script: if GET == ARGV[1] then DEL
        v = await self.get(key)
        if v == token:
            del self.store[key]
            return 1
        return 0

    async def delete(self, key):
        if key in self.store:
            del self.store[key]


async def test_lock_acquire_release():
    r = FakeRedis()
    lock = DistributedLock(r, key="lock:1", ttl_ms=5000)
    await lock.__aenter__()
    assert await r.get("lock:1") is not None
    await lock.__aexit__(None, None, None)
    assert "lock:1" not in r.store


async def test_lock_already_held_raises():
    r = FakeRedis()
    await r.set("lock:1", "other-token", nx=True, px=5000)
    lock = DistributedLock(r, key="lock:1", ttl_ms=5000)
    with pytest.raises(LockAcquireError):
        await lock.__aenter__()


async def test_lock_only_holder_can_release():
    r = FakeRedis()
    # Holder A acquires
    lock_a = DistributedLock(r, key="lock:1", ttl_ms=5000)
    await lock_a.__aenter__()
    # Someone else overwrites the key directly
    await r.set("lock:1", "intruder", px=5000)
    # A's __aexit__ should NOT delete intruder's token
    await lock_a.__aexit__(None, None, None)
    assert await r.get("lock:1") == "intruder"
```

- [ ] **Step 2: Run test, verify it fails**

```bash
cd backend && uv run pytest tests/unit/test_concurrency.py -v
```
Expected: `ModuleNotFoundError: No module named 'app.core.concurrency'`

- [ ] **Step 3: Write `concurrency.py`**

Create `backend/app/core/concurrency.py`:

```python
"""Distributed lock with Lua release + retry helpers."""
from __future__ import annotations

import asyncio
import secrets
from collections.abc import Awaitable, Callable
from contextlib import AbstractAsyncContextManager
from typing import Any, TypeVar

T = TypeVar("T")


class LockAcquireError(Exception):
    """Raised when a distributed lock cannot be acquired."""


_RELEASE_SCRIPT = """
if redis.call('GET', KEYS[1]) == ARGV[1] then
    return redis.call('DEL', KEYS[1])
else
    return 0
end
"""


class DistributedLock(AbstractAsyncContextManager):
    """Async distributed lock (SET NX PX + Lua release).

    Usage:
        lock = DistributedLock(redis, key="seat:42", ttl_ms=3000)
        async with lock:
            ...
    """

    def __init__(self, redis: Any, *, key: str, ttl_ms: int):
        self.redis = redis
        self.key = key
        self.ttl_ms = ttl_ms
        self.token = secrets.token_hex(16)
        self._held = False

    async def __aenter__(self) -> "DistributedLock":
        ok = await self.redis.set(self.key, self.token, nx=True, px=self.ttl_ms)
        if not ok:
            raise LockAcquireError(f"Lock '{self.key}' is held by another holder")
        self._held = True
        return self

    async def __aexit__(self, exc_type, exc, tb) -> None:
        if self._held:
            try:
                await self.redis.eval(_RELEASE_SCRIPT, 1, self.key, self.token)
            finally:
                self._held = False


async def acquire_with_retry(
    lock_factory: Callable[[], AbstractAsyncContextManager],
    *,
    max_retries: int = 3,
    backoff_ms: list[int] | None = None,
) -> AbstractAsyncContextManager:
    """Acquire a lock with exponential backoff. Raises LockAcquireError after max_retries.

    Args:
        lock_factory: callable returning a new lock context manager each attempt
        max_retries: total attempts (1 = try once, no retry)
        backoff_ms: sleep before each retry; default [100, 200, 400]
    """
    if backoff_ms is None:
        backoff_ms = [100, 200, 400]
    last_error: LockAcquireError | None = None
    for attempt in range(max_retries):
        lock = lock_factory()
        try:
            await lock.__aenter__()
            return lock
        except LockAcquireError as e:
            last_error = e
            if attempt < max_retries - 1:
                await asyncio.sleep(backoff_ms[min(attempt, len(backoff_ms) - 1)] / 1000)
    raise last_error or LockAcquireError("acquire_with_retry exhausted")
```

- [ ] **Step 4: Run tests, verify pass**

```bash
cd backend && uv run pytest tests/unit/test_concurrency.py -v
```
Expected: 3 tests pass

- [ ] **Step 5: Commit**

```bash
git add backend/app/core/concurrency.py backend/tests/unit/test_concurrency.py
git commit -m "feat(concurrency): DistributedLock (SET NX PX + Lua release) + retry helper"
```

---

### Task 3: Async retry helper

**Files:**
- Create: `backend/app/core/retry.py`
- Create: `backend/tests/unit/test_retry.py`

- [ ] **Step 1: Write the failing test**

Create `backend/tests/unit/test_retry.py`:

```python
import asyncio
import pytest

from app.core.retry import retry_async, RetryExhausted


async def test_retry_succeeds_first_try():
    calls = []

    async def fn():
        calls.append(1)
        return "ok"

    result = await retry_async(fn, max_attempts=3, backoff_ms=[1, 1, 1])
    assert result == "ok"
    assert len(calls) == 1


async def test_retry_then_succeed():
    calls = []

    async def fn():
        calls.append(1)
        if len(calls) < 3:
            raise ValueError("transient")
        return "ok"

    result = await retry_async(fn, max_attempts=3, backoff_ms=[1, 1, 1])
    assert result == "ok"
    assert len(calls) == 3


async def test_retry_exhausted_raises():
    async def fn():
        raise ValueError("nope")

    with pytest.raises(RetryExhausted):
        await retry_async(fn, max_attempts=3, backoff_ms=[1, 1, 1])


async def test_retry_only_catches_specific_exceptions():
    async def fn():
        raise KeyError("nope")

    # KeyError not in retry_on -> raised immediately, not wrapped
    with pytest.raises(KeyError):
        await retry_async(fn, max_attempts=3, backoff_ms=[1, 1, 1], retry_on=(ValueError,))
```

- [ ] **Step 2: Run, verify fails**

```bash
cd backend && uv run pytest tests/unit/test_retry.py -v
```
Expected: `ModuleNotFoundError`

- [ ] **Step 3: Write `retry.py`**

Create `backend/app/core/retry.py`:

```python
"""Async retry with exponential backoff."""
from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable
from typing import TypeVar

T = TypeVar("T")


class RetryExhausted(Exception):
    """Raised when all retry attempts fail."""

    def __init__(self, last_exception: BaseException, attempts: int):
        super().__init__(f"Retry exhausted after {attempts} attempts: {last_exception!r}")
        self.last_exception = last_exception
        self.attempts = attempts


async def retry_async(
    fn: Callable[[], Awaitable[T]],
    *,
    max_attempts: int = 3,
    backoff_ms: list[int] | None = None,
    retry_on: tuple[type[BaseException], ...] = (Exception,),
) -> T:
    """Call `fn` with exponential-backoff retry.

    Args:
        fn: zero-arg async callable
        max_attempts: total attempts (1 = no retry)
        backoff_ms: sleep BEFORE retry #N; default [100, 300, 900]
        retry_on: exception types to catch & retry
    """
    if backoff_ms is None:
        backoff_ms = [100, 300, 900]
    last_exc: BaseException | None = None
    for attempt in range(1, max_attempts + 1):
        try:
            return await fn()
        except retry_on as e:
            last_exc = e
            if attempt < max_attempts:
                idx = min(attempt - 1, len(backoff_ms) - 1)
                await asyncio.sleep(backoff_ms[idx] / 1000)
    assert last_exc is not None
    raise RetryExhausted(last_exc, max_attempts)
```

- [ ] **Step 4: Run tests, verify pass**

```bash
cd backend && uv run pytest tests/unit/test_retry.py -v
```
Expected: 4 tests pass

- [ ] **Step 5: Commit**

```bash
git add backend/app/core/retry.py backend/tests/unit/test_retry.py
git commit -m "feat(retry): async retry with exponential backoff"
```

---

### Task 4: Wire Redis init into FastAPI lifespan

**Files:**
- Modify: `backend/app/main.py`

- [ ] **Step 1: Update `main.py` to init/dispose Redis**

Replace the `lifespan` function in `backend/app/main.py`:

```python
@asynccontextmanager
async def lifespan(app: FastAPI):
    init_observability()
    init_engine()
    init_redis()
    yield
    await dispose_engine()
    await dispose_redis()
    shutdown_observability()
```

And add imports at the top:

```python
from app.clients.redis_client import dispose_redis, init_redis
```

- [ ] **Step 2: Verify app still imports**

```bash
cd backend && uv run python -c "from app.main import app; print('OK')"
```
Expected: `OK`

- [ ] **Step 3: Run all unit tests**

```bash
cd backend && uv run pytest tests/unit -v
```
Expected: all 15 + 3 + 4 = 22 tests pass

- [ ] **Step 4: Commit**

```bash
git add backend/app/main.py
git commit -m "feat(app): wire Redis init/dispose into FastAPI lifespan"
```

---

## Phase 2: Document Loading + Chunking

### Task 5: Document loaders

**Files:**
- Create: `backend/app/rag/__init__.py`
- Create: `backend/app/rag/loaders.py`
- Create: `backend/tests/unit/test_loaders.py`

- [ ] **Step 1: Add loader deps**

```bash
cd backend && uv add "pypdf>=5.0.0" "python-docx>=1.1.0"
```

- [ ] **Step 2: Write the failing test**

Create `backend/tests/unit/test_loaders.py`:

```python
from pathlib import Path

import pytest

from app.rag.loaders import load_document, UnsupportedFormatError


def test_load_text(tmp_path: Path):
    f = tmp_path / "doc.txt"
    f.write_text("hello world", encoding="utf-8")
    pages = load_document(f)
    assert len(pages) == 1
    assert pages[0] == "hello world"


def test_load_markdown(tmp_path: Path):
    f = tmp_path / "doc.md"
    f.write_text("# Title\n\nBody", encoding="utf-8")
    pages = load_document(f)
    assert pages == ["# Title\n\nBody"]


def test_unsupported_format_raises(tmp_path: Path):
    f = tmp_path / "doc.xyz"
    f.write_text("x", encoding="utf-8")
    with pytest.raises(UnsupportedFormatError):
        load_document(f)


def test_load_docx(tmp_path: Path):
    from docx import Document
    f = tmp_path / "doc.docx"
    doc = Document()
    doc.add_paragraph("paragraph one")
    doc.add_paragraph("paragraph two")
    doc.save(f)
    pages = load_document(f)
    assert len(pages) == 1
    assert "paragraph one" in pages[0]
    assert "paragraph two" in pages[0]


def test_load_pdf(tmp_path: Path):
    # Use a real PDF if pypdf can find one; skip if generation is too involved
    pytest.importorskip("pypdf")
    # Minimal: write a 1-page PDF using pypdf's writer
    from pypdf import PdfWriter
    f = tmp_path / "doc.pdf"
    writer = PdfWriter()
    writer.add_blank_page(width=72, height=72)
    # pypdf cannot write text easily without reportlab; skip real content
    writer.write(str(f))
    pages = load_document(f)
    # blank page returns empty string
    assert isinstance(pages, list)
```

- [ ] **Step 3: Run, verify fails**

```bash
cd backend && uv run pytest tests/unit/test_loaders.py -v
```
Expected: `ModuleNotFoundError`

- [ ] **Step 4: Write `loaders.py`**

Create `backend/app/rag/__init__.py`:

```python
"""RAG pipeline (loaders, chunker, BM25, dense, RRF, rerank, hybrid)."""
```

Create `backend/app/rag/loaders.py`:

```python
"""Document loaders: .pdf / .docx / .txt / .md → list[str] of page-level text."""
from __future__ import annotations

from pathlib import Path


class UnsupportedFormatError(Exception):
    """Raised when a file extension has no registered loader."""


def load_document(path: Path | str) -> list[str]:
    """Load a document, returning one string per page/section.

    For .txt / .md → single-element list with full content.
    For .pdf → one element per page.
    For .docx → one element with paragraphs joined by '\n\n'.
    """
    p = Path(path)
    suffix = p.suffix.lower()
    if suffix in (".txt", ".md"):
        return [p.read_text(encoding="utf-8")]
    if suffix == ".pdf":
        return _load_pdf(p)
    if suffix == ".docx":
        return _load_docx(p)
    raise UnsupportedFormatError(f"No loader for extension: {suffix}")


def _load_pdf(p: Path) -> list[str]:
    from pypdf import PdfReader

    reader = PdfReader(str(p))
    return [(page.extract_text() or "") for page in reader.pages]


def _load_docx(p: Path) -> list[str]:
    from docx import Document

    doc = Document(str(p))
    paragraphs = [para.text for para in doc.paragraphs if para.text.strip()]
    return ["\n\n".join(paragraphs)]
```

- [ ] **Step 5: Run tests, verify pass**

```bash
cd backend && uv run pytest tests/unit/test_loaders.py -v
```
Expected: 5 tests pass (4 main + pdf minimal)

- [ ] **Step 6: Commit**

```bash
git add backend/app/rag/ backend/tests/unit/test_loaders.py backend/pyproject.toml backend/uv.lock
git commit -m "feat(rag): document loaders (txt/md/pdf/docx)"
```

---

### Task 6: Sliding-window chunker

**Files:**
- Create: `backend/app/rag/chunker.py`
- Create: `backend/tests/unit/test_chunker.py`

- [ ] **Step 1: Write the failing test**

Create `backend/tests/unit/test_chunker.py`:

```python
from app.rag.chunker import Chunk, chunk_text


def test_short_text_single_chunk():
    text = "hello world"
    chunks = chunk_text(text)
    assert len(chunks) == 1
    assert chunks[0].content == "hello world"


def test_respects_max_chunk_size():
    text = "a" * 1500
    chunks = chunk_text(text, chunk_size=500, overlap=80)
    assert len(chunks) >= 3
    for c in chunks:
        assert len(c.content) <= 500


def test_overlap_between_consecutive_chunks():
    text = ("word " * 200).strip()  # 1000 chars
    chunks = chunk_text(text, chunk_size=200, overlap=50)
    assert len(chunks) >= 4
    # Last `overlap` chars of chunk[i] should appear at start of chunk[i+1]
    for a, b in zip(chunks, chunks[1:]):
        tail = a.content[-50:]
        head = b.content[:50]
        assert tail in head or head.startswith(tail[:25])


def test_chunks_have_offsets():
    text = "abcdefghij" * 100  # 1000 chars
    chunks = chunk_text(text, chunk_size=300, overlap=50)
    for c in chunks:
        assert isinstance(c.start_offset, int)
        assert isinstance(c.end_offset, int)
        assert 0 <= c.start_offset < c.end_offset <= len(text)


def test_empty_text_returns_empty_list():
    assert chunk_text("") == []
```

- [ ] **Step 2: Run, verify fails**

```bash
cd backend && uv run pytest tests/unit/test_chunker.py -v
```
Expected: `ModuleNotFoundError`

- [ ] **Step 3: Write `chunker.py`**

Create `backend/app/rag/chunker.py`:

```python
"""Sliding-window text chunker."""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Chunk:
    content: str
    start_offset: int
    end_offset: int
    chunk_id: str  # sha1 of content


def chunk_text(
    text: str,
    *,
    chunk_size: int = 500,
    overlap: int = 80,
    min_chunk: int = 100,
) -> list[Chunk]:
    """Split text into overlapping chunks.

    Args:
        text: input string
        chunk_size: target chunk size in characters
        overlap: overlap between consecutive chunks
        min_chunk: drop trailing chunks shorter than this (unless it's the only chunk)
    """
    text = text.strip()
    if not text:
        return []

    chunks: list[Chunk] = []
    step = chunk_size - overlap
    if step <= 0:
        raise ValueError("chunk_size must be > overlap")

    start = 0
    while start < len(text):
        end = min(start + chunk_size, len(text))
        content = text[start:end]
        if len(content) >= min_chunk or not chunks:
            chunk_id = _hash(content)
            chunks.append(Chunk(content=content, start_offset=start, end_offset=end, chunk_id=chunk_id))
        if end == len(text):
            break
        start += step
    return chunks


def _hash(content: str) -> str:
    import hashlib
    return hashlib.sha1(content.encode("utf-8")).hexdigest()
```

- [ ] **Step 4: Run tests, verify pass**

```bash
cd backend && uv run pytest tests/unit/test_chunker.py -v
```
Expected: 5 tests pass

- [ ] **Step 5: Commit**

```bash
git add backend/app/rag/chunker.py backend/tests/unit/test_chunker.py
git commit -m "feat(rag): sliding-window chunker with offsets"
```

---

## Phase 3: BM25 Retriever

### Task 7: Whoosh index manager

**Files:**
- Create: `backend/app/rag/bm25_index.py`

- [ ] **Step 1: Write `bm25_index.py`**

Create `backend/app/rag/bm25_index.py`:

```python
"""Whoosh index manager — one index per tenant, persisted to disk."""
from __future__ import annotations

from pathlib import Path
from uuid import UUID

from whoosh import index
from whoosh.analysis import StemmingAnalyzer
from whoosh.fields import ID, TEXT, Schema
from whoosh.qparser import MultifieldParser

_SCHEMA = Schema(
    chunk_id=ID(stored=True, unique=True),
    tenant_id=ID(stored=True),
    source_id=ID(stored=True),
    title=TEXT(stored=True),
    content=TEXT(stored=True, analyzer=StemmingAnalyzer()),
)


class WhooshIndexManager:
    """Owns Whoosh indexes under a base directory, one subdir per tenant."""

    def __init__(self, base_dir: Path | str):
        self.base_dir = Path(base_dir)
        self.base_dir.mkdir(parents=True, exist_ok=True)

    def _tenant_dir(self, tenant_id: UUID) -> Path:
        d = self.base_dir / str(tenant_id)
        d.mkdir(parents=True, exist_ok=True)
        return d

    def get_index(self, tenant_id: UUID):
        """Open or create the tenant's index."""
        d = self._tenant_dir(tenant_id)
        ix = index.open_dir(str(d)) if index.exists_in(str(d)) else index.create_in(str(d), _SCHEMA)
        return ix

    def add_chunks(
        self,
        tenant_id: UUID,
        chunks: list[tuple[str, str, str, str]],  # (chunk_id, source_id, title, content)
    ) -> None:
        """Bulk-add chunks. chunk_id is the dedup key."""
        ix = self.get_index(tenant_id)
        writer = ix.writer()
        for chunk_id, source_id, title, content in chunks:
            writer.update_document(
                chunk_id=chunk_id,
                tenant_id=str(tenant_id),
                source_id=source_id,
                title=title,
                content=content,
            )
        writer.commit()

    def delete_by_source(self, tenant_id: UUID, source_id: str) -> None:
        """Remove all chunks belonging to a source."""
        ix = self.get_index(tenant_id)
        writer = ix.writer()
        writer.delete_by_term("source_id", source_id)
        writer.commit()

    def search(self, tenant_id: UUID, query: str, top_k: int = 20) -> list[dict]:
        """Search and return list of {chunk_id, source_id, title, content, score}."""
        ix = self.get_index(tenant_id)
        parser = MultifieldParser(["title", "content"], schema=ix.schema)
        parsed = parser.parse(query)
        results: list[dict] = []
        with ix.searcher() as searcher:
            hits = searcher.search(parsed, limit=top_k)
            for hit in hits:
                results.append(
                    {
                        "chunk_id": hit["chunk_id"],
                        "source_id": hit["source_id"],
                        "title": hit.get("title", ""),
                        "content": hit["content"],
                        "score": float(hit.score),
                    }
                )
        return results
```

- [ ] **Step 2: Smoke test in REPL**

```bash
cd backend && uv run python -c "
from uuid import uuid4
from pathlib import Path
import tempfile
from app.rag.bm25_index import WhooshIndexManager

with tempfile.TemporaryDirectory() as tmp:
    mgr = WhooshIndexManager(Path(tmp))
    tid = uuid4()
    mgr.add_chunks(tid, [
        ('c1', 'src1', '借阅规则', '本科生最多借 10 本,期限 30 天'),
        ('c2', 'src1', '逾期罚款', '逾期一天罚款 0.5 元'),
    ])
    results = mgr.search(tid, '借阅 本科生', top_k=5)
    print('Hits:', len(results))
    for r in results:
        print(' ', r['chunk_id'], r['title'])
"
```
Expected: `Hits: 2` and both chunk IDs printed

- [ ] **Step 3: Commit**

```bash
git add backend/app/rag/bm25_index.py
git commit -m "feat(rag): Whoosh BM25 index manager (per-tenant, disk-persisted)"
```

---

### Task 8: BM25 retriever wrapper

**Files:**
- Create: `backend/app/rag/bm25_retriever.py`

- [ ] **Step 1: Write `bm25_retriever.py`**

Create `backend/app/rag/bm25_retriever.py`:

```python
"""BM25 retriever — wraps WhooshIndexManager and yields Hit objects."""
from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID

from app.rag.bm25_index import WhooshIndexManager


@dataclass(frozen=True)
class Hit:
    chunk_id: str
    source_id: str
    title: str
    content: str
    score: float
    rank: int  # 1-based rank within this retriever


class BM25Retriever:
    def __init__(self, index_manager: WhooshIndexManager):
        self.index_manager = index_manager

    async def retrieve(self, query: str, tenant_id: UUID, top_k: int = 20) -> list[Hit]:
        raw = self.index_manager.search(tenant_id, query, top_k=top_k)
        return [
            Hit(
                chunk_id=r["chunk_id"],
                source_id=r["source_id"],
                title=r["title"],
                content=r["content"],
                score=r["score"],
                rank=i + 1,
            )
            for i, r in enumerate(raw)
        ]
```

- [ ] **Step 2: Verify import**

```bash
cd backend && uv run python -c "from app.rag.bm25_retriever import BM25Retriever, Hit; print('OK')"
```
Expected: `OK`

- [ ] **Step 3: Commit**

```bash
git add backend/app/rag/bm25_retriever.py
git commit -m "feat(rag): BM25Retriever returning Hit dataclass"
```

---

## Phase 4: Dense Retriever (ChromaDB)

### Task 9: ChromaDB client wrapper

**Files:**
- Create: `backend/app/rag/chroma_store.py`

- [ ] **Step 1: Add ChromaDB dep**

```bash
cd backend && uv add "chromadb>=1.0.0"
```

- [ ] **Step 2: Write `chroma_store.py`**

Create `backend/app/rag/chroma_store.py`:

```python
"""ChromaDB persistent client — one collection per tenant."""
from __future__ import annotations

from pathlib import Path
from uuid import UUID

import chromadb
from chromadb.config import Settings as ChromaSettings


class ChromaStore:
    """Wraps a persistent ChromaDB client; collections are named `library_{tenant_id}`."""

    def __init__(self, persist_dir: Path | str):
        self.persist_dir = Path(persist_dir)
        self.persist_dir.mkdir(parents=True, exist_ok=True)
        self.client = chromadb.PersistentClient(
            path=str(self.persist_dir),
            settings=ChromaSettings(anonymized_telemetry=False, allow_reset=False),
        )

    def collection_name(self, tenant_id: UUID) -> str:
        return f"library_{tenant_id.hex}"

    def get_or_create(self, tenant_id: UUID):
        name = self.collection_name(tenant_id)
        return self.client.get_or_create_collection(
            name=name,
            metadata={"tenant_id": str(tenant_id)},
        )

    def upsert(
        self,
        tenant_id: UUID,
        *,
        ids: list[str],
        embeddings: list[list[float]],
        documents: list[str],
        metadatas: list[dict],
    ) -> None:
        coll = self.get_or_create(tenant_id)
        coll.upsert(ids=ids, embeddings=embeddings, documents=documents, metadatas=metadatas)

    def delete_by_source(self, tenant_id: UUID, source_id: str) -> None:
        coll = self.get_or_create(tenant_id)
        coll.delete(where={"source_id": source_id})

    def query(
        self,
        tenant_id: UUID,
        *,
        query_embedding: list[float],
        top_k: int = 20,
    ) -> list[dict]:
        coll = self.get_or_create(tenant_id)
        results = coll.query(query_embeddings=[query_embedding], n_results=top_k)
        hits: list[dict] = []
        # ChromaDB returns parallel arrays; transpose
        ids = results.get("ids", [[]])[0]
        docs = results.get("documents", [[]])[0]
        metas = results.get("metadatas", [[]])[0]
        distances = results.get("distances", [[]])[0]
        for i, chunk_id in enumerate(ids):
            hits.append(
                {
                    "chunk_id": chunk_id,
                    "content": docs[i] if i < len(docs) else "",
                    "source_id": (metas[i] or {}).get("source_id", ""),
                    "title": (metas[i] or {}).get("title", ""),
                    "score": 1.0 - distances[i] if i < len(distances) else 0.0,  # cosine distance → similarity
                }
            )
        return hits
```

- [ ] **Step 3: Verify import**

```bash
cd backend && uv run python -c "from app.rag.chroma_store import ChromaStore; print('OK')"
```
Expected: `OK`

- [ ] **Step 4: Commit**

```bash
git add backend/app/rag/chroma_store.py backend/pyproject.toml backend/uv.lock
git commit -m "feat(rag): ChromaStore (persistent client, per-tenant collections)"
```

---

### Task 10: Embedding client (Qwen)

**Files:**
- Create: `backend/app/clients/embedding_client.py`

- [ ] **Step 1: Add DashScope OpenAI dep (already installed in root project; add here too)**

```bash
cd backend && uv add "openai>=1.50.0"
```

- [ ] **Step 2: Write `embedding_client.py`**

Create `backend/app/clients/embedding_client.py`:

```python
"""Qwen text-embedding-v2 via DashScope OpenAI-compatible API.

Per spec ADR-006: Chinese-friendly + native.
Per MVP (ADR-001): single embedding model; interface ready for multi-modal later.
"""
from __future__ import annotations

from collections.abc import Sequence

from openai import AsyncOpenAI

from app.core.config import get_settings
from app.core.retry import retry_async


class EmbeddingClient:
    def __init__(self, model: str = "text-embedding-v2"):
        settings = get_settings()
        # DashScope OpenAI-compatible endpoint
        self.client = AsyncOpenAI(
            api_key=settings.dashscope_api_key,
            base_url="https://dashscope.aliyuncs.com/compatible-mode/v1",
        )
        self.model = model
        self.batch_size = 32

    async def embed(self, texts: Sequence[str]) -> list[list[float]]:
        """Embed a batch of texts. Auto-splits into chunks of self.batch_size."""
        if not texts:
            return []
        out: list[list[float]] = []
        for i in range(0, len(texts), self.batch_size):
            chunk = list(texts[i : i + self.batch_size])
            response = await retry_async(
                lambda c=chunk: self._embed_once(c),
                max_attempts=3,
                retry_on=(Exception,),
            )
            out.extend(response)
        return out

    async def _embed_once(self, texts: list[str]) -> list[list[float]]:
        # OpenAI-compatible: input is list[str], data[i].embedding is the vector
        result = await self.client.embeddings.create(model=self.model, input=texts)
        return [item.embedding for item in result.data]
```

- [ ] **Step 3: Add `dashscope_api_key` to settings**

Modify `backend/app/core/config.py` — add to `Settings`:

```python
    # External APIs
    dashscope_api_key: str = Field(default="sk-placeholder", min_length=1)
```

Also add to `backend/.env.example`:

```bash
DASHSCOPE_API_KEY=sk-placeholder
```

- [ ] **Step 4: Verify import + setting**

```bash
cd backend && uv run python -c "from app.clients.embedding_client import EmbeddingClient; from app.core.config import get_settings; print(get_settings().dashscope_api_key[:6])"
```
Expected: prints first 6 chars of the key (or "sk-pla" for placeholder)

- [ ] **Step 5: Commit**

```bash
git add backend/app/clients/embedding_client.py backend/app/core/config.py backend/.env.example backend/pyproject.toml backend/uv.lock
git commit -m "feat(clients): EmbeddingClient (Qwen text-embedding-v2 via DashScope)"
```

---

### Task 11: Dense retriever

**Files:**
- Create: `backend/app/rag/dense_retriever.py`

- [ ] **Step 1: Write `dense_retriever.py`**

Create `backend/app/rag/dense_retriever.py`:

```python
"""Dense retriever — embeds query, queries ChromaDB, returns Hit list."""
from __future__ import annotations

from uuid import UUID

from app.clients.embedding_client import EmbeddingClient
from app.rag.bm25_retriever import Hit
from app.rag.chroma_store import ChromaStore


class DenseRetriever:
    def __init__(self, chroma: ChromaStore, embedding: EmbeddingClient):
        self.chroma = chroma
        self.embedding = embedding

    async def retrieve(self, query: str, tenant_id: UUID, top_k: int = 20) -> list[Hit]:
        vectors = await self.embedding.embed([query])
        if not vectors:
            return []
        raw = self.chroma.query(tenant_id, query_embedding=vectors[0], top_k=top_k)
        return [
            Hit(
                chunk_id=r["chunk_id"],
                source_id=r["source_id"],
                title=r["title"],
                content=r["content"],
                score=r["score"],
                rank=i + 1,
            )
            for i, r in enumerate(raw)
        ]
```

- [ ] **Step 2: Verify import**

```bash
cd backend && uv run python -c "from app.rag.dense_retriever import DenseRetriever; print('OK')"
```
Expected: `OK`

- [ ] **Step 3: Commit**

```bash
git add backend/app/rag/dense_retriever.py
git commit -m "feat(rag): DenseRetriever (ChromaDB + Qwen embedding)"
```

---

## Phase 5: RRF + Rerank + Hybrid Pipeline

### Task 12: RRF fusion (pure function)

**Files:**
- Create: `backend/app/rag/rrf.py`
- Create: `backend/tests/unit/test_rrf.py`

- [ ] **Step 1: Write the failing test**

Create `backend/tests/unit/test_rrf.py`:

```python
from app.rag.bm25_retriever import Hit
from app.rag.rrf import reciprocal_rank_fusion


def _hit(cid: str, rank: int, score: float = 1.0) -> Hit:
    return Hit(chunk_id=cid, source_id="s", title="", content=f"content-{cid}", score=score, rank=rank)


def test_rrf_single_list_preserves_order():
    hits = [_hit("a", 1), _hit("b", 2), _hit("c", 3)]
    fused = reciprocal_rank_fusion([hits], k=60)
    assert [h.chunk_id for h in fused] == ["a", "b", "c"]


def test_rrf_appears_in_multiple_lists_boosted():
    bm25 = [_hit("a", 1), _hit("b", 2)]
    dense = [_hit("b", 1), _hit("c", 2)]
    fused = reciprocal_rank_fusion([bm25, dense], k=60)
    # 'b' appears in both → highest RRF score
    assert fused[0].chunk_id == "b"


def test_rrf_k_parameter_affects_scores():
    hits = [_hit("a", 1)]
    fused_low = reciprocal_rank_fusion([hits], k=10)
    fused_high = reciprocal_rank_fusion([hits], k=100)
    assert fused_low[0].score > fused_high[0].score


def test_rrf_empty_lists():
    assert reciprocal_rank_fusion([]) == []
    assert reciprocal_rank_fusion([[]]) == []


def test_rrf_picks_longer_content_for_duplicates():
    """When the same chunk_id appears in multiple lists with different content,
    RRF should keep the longest version."""
    short = _hit("x", 1)
    long = Hit(chunk_id="x", source_id="s", title="", content="a" * 500, score=1.0, rank=1)
    fused = reciprocal_rank_fusion([[short], [long]], k=60)
    assert fused[0].content == "a" * 500
```

- [ ] **Step 2: Run, verify fails**

```bash
cd backend && uv run pytest tests/unit/test_rrf.py -v
```
Expected: `ModuleNotFoundError`

- [ ] **Step 3: Write `rrf.py`**

Create `backend/app/rag/rrf.py`:

```python
"""Reciprocal Rank Fusion — pure function, no I/O."""
from __future__ import annotations

from collections import defaultdict

from app.rag.bm25_retriever import Hit


def reciprocal_rank_fusion(
    hit_lists: list[list[Hit]],
    *,
    k: int = 60,
) -> list[Hit]:
    """Fuse multiple ranked lists into one via RRF.

    score(d) = Σ 1 / (k + rank_i(d))

    For duplicate chunk_ids across lists, keeps the longest content version.
    """
    rrf_scores: dict[str, float] = defaultdict(float)
    hit_map: dict[str, Hit] = {}

    for hits in hit_lists:
        for rank, hit in enumerate(hits, start=1):
            rrf_scores[hit.chunk_id] += 1.0 / (k + rank)
            existing = hit_map.get(hit.chunk_id)
            if existing is None or len(hit.content) > len(existing.content):
                hit_map[hit.chunk_id] = hit

    sorted_ids = sorted(rrf_scores.keys(), key=lambda cid: rrf_scores[cid], reverse=True)
    return [
        Hit(
            chunk_id=cid,
            source_id=hit_map[cid].source_id,
            title=hit_map[cid].title,
            content=hit_map[cid].content,
            score=rrf_scores[cid],
            rank=i + 1,
        )
        for i, cid in enumerate(sorted_ids)
    ]
```

- [ ] **Step 4: Run tests, verify pass**

```bash
cd backend && uv run pytest tests/unit/test_rrf.py -v
```
Expected: 5 tests pass

- [ ] **Step 5: Commit**

```bash
git add backend/app/rag/rrf.py backend/tests/unit/test_rrf.py
git commit -m "feat(rag): RRF fusion (pure function, dedup by longest content)"
```

---

### Task 13: Rerank client (Qwen3-rerank)

**Files:**
- Create: `backend/app/clients/rerank_client.py`

- [ ] **Step 1: Add DashScope native SDK**

```bash
cd backend && uv add "dashscope>=1.20.0"
```

- [ ] **Step 2: Write `rerank_client.py`**

Create `backend/app/clients/rerank_client.py`:

```python
"""Qwen qwen3-rerank via DashScope native endpoint.

Note: NOT OpenAI-compatible — uses DashScope Generation API.
"""
from __future__ import annotations

import asyncio
from collections.abc import Sequence

import dashscope
from dashscope import TextReRank

from app.core.config import get_settings
from app.core.retry import retry_async


class RerankClient:
    def __init__(self, model: str = "qwen3-rerank"):
        settings = get_settings()
        dashscope.api_key = settings.dashscope_api_key
        self.model = model
        self.batch_size = 10

    async def rerank(
        self,
        query: str,
        documents: Sequence[str],
        *,
        top_n: int = 5,
    ) -> list[tuple[int, float]]:
        """Rerank documents by relevance to query.

        Returns list of (original_index, relevance_score), sorted by score desc.
        """
        if not documents:
            return []
        # DashScope TextReRank is sync; run in executor to avoid blocking event loop
        loop = asyncio.get_running_loop()
        results = await retry_async(
            lambda: loop.run_in_executor(None, self._rerank_sync, query, list(documents), top_n),
            max_attempts=3,
            retry_on=(Exception,),
        )
        return results

    def _rerank_sync(self, query: str, documents: list[str], top_n: int) -> list[tuple[int, float]]:
        # DashScope SDK returns Response object with .output.results
        resp = TextReRank.call(
            model=self.model,
            query=query,
            documents=documents,
            top_n=min(top_n, len(documents)),
            return_documents=False,
        )
        if getattr(resp, "status_code", 200) != 200:
            raise RuntimeError(f"Rerank failed: {getattr(resp, 'message', 'unknown')}")
        out: list[tuple[int, float]] = []
        for item in resp.output.results:
            out.append((int(item["index"]), float(item["relevance_score"])))
        out.sort(key=lambda x: x[1], reverse=True)
        return out
```

- [ ] **Step 3: Verify import**

```bash
cd backend && uv run python -c "from app.clients.rerank_client import RerankClient; print('OK')"
```
Expected: `OK`

- [ ] **Step 4: Commit**

```bash
git add backend/app/clients/rerank_client.py backend/pyproject.toml backend/uv.lock
git commit -m "feat(clients): RerankClient (Qwen qwen3-rerank via DashScope native)"
```

---

### Task 14: Hybrid retriever orchestrator

**Files:**
- Create: `backend/app/rag/pipeline.py`

- [ ] **Step 1: Write `pipeline.py`**

Create `backend/app/rag/pipeline.py`:

```python
"""HybridRetriever: BM25 + Dense (concurrent) → RRF → Rerank → top-K."""
from __future__ import annotations

import asyncio
from dataclasses import dataclass
from uuid import UUID

from app.clients.rerank_client import RerankClient
from app.rag.bm25_retriever import BM25Retriever, Hit
from app.rag.dense_retriever import DenseRetriever
from app.rag.rrf import reciprocal_rank_fusion


@dataclass(frozen=True)
class RetrievalResult:
    query: str
    hits: list[Hit]  # post-rerank, top_k


class HybridRetriever:
    def __init__(
        self,
        bm25: BM25Retriever,
        dense: DenseRetriever,
        rerank: RerankClient,
        *,
        bm25_top_k: int = 20,
        dense_top_k: int = 20,
        rrf_top_k: int = 30,
        rerank_top_k: int = 5,
    ):
        self.bm25 = bm25
        self.dense = dense
        self.rerank = rerank
        self.bm25_top_k = bm25_top_k
        self.dense_top_k = dense_top_k
        self.rrf_top_k = rrf_top_k
        self.rerank_top_k = rerank_top_k

    async def retrieve(self, query: str, tenant_id: UUID) -> RetrievalResult:
        # Stage 1: BM25 + Dense in parallel (failure-tolerant)
        bm25_hits, dense_hits = await asyncio.gather(
            self.bm25.retrieve(query, tenant_id, top_k=self.bm25_top_k),
            self.dense.retrieve(query, tenant_id, top_k=self.dense_top_k),
            return_exceptions=True,
        )
        if isinstance(bm25_hits, Exception):
            bm25_hits = []
        if isinstance(dense_hits, Exception):
            dense_hits = []

        # Stage 2: RRF fusion
        fused = reciprocal_rank_fusion([bm25_hits, dense_hits])[: self.rrf_top_k]
        if not fused:
            return RetrievalResult(query=query, hits=[])

        # Stage 3: Rerank
        documents = [h.content for h in fused]
        reranked = await self.rerank.rerank(query, documents, top_n=self.rerank_top_k)
        # Map reranked indices back to fused hits, attach new score
        out: list[Hit] = []
        for orig_idx, new_score in reranked:
            base = fused[orig_idx]
            out.append(
                Hit(
                    chunk_id=base.chunk_id,
                    source_id=base.source_id,
                    title=base.title,
                    content=base.content,
                    score=new_score,
                    rank=len(out) + 1,
                )
            )
        return RetrievalResult(query=query, hits=out)
```

- [ ] **Step 2: Verify import**

```bash
cd backend && uv run python -c "from app.rag.pipeline import HybridRetriever, RetrievalResult; print('OK')"
```
Expected: `OK`

- [ ] **Step 3: Commit**

```bash
git add backend/app/rag/pipeline.py
git commit -m "feat(rag): HybridRetriever (BM25+Dense concurrent → RRF → Rerank)"
```

---

## Phase 6: Book Service + Endpoints

### Task 15: Pagination schema

**Files:**
- Create: `backend/app/schemas/pagination.py`

- [ ] **Step 1: Write `pagination.py`**

Create `backend/app/schemas/pagination.py`:

```python
"""Pagination request/response schemas."""
from __future__ import annotations

from typing import Generic, TypeVar

from pydantic import BaseModel, Field

T = TypeVar("T")


class PageRequest(BaseModel):
    page: int = Field(default=1, ge=1)
    page_size: int = Field(default=20, ge=1, le=100)


class Page(BaseModel, Generic[T]):
    items: list[T]
    page: int
    page_size: int
    total: int
```

- [ ] **Step 2: Commit**

```bash
git add backend/app/schemas/pagination.py
git commit -m "feat(schemas): pagination request/response"
```

---

### Task 16: Book schemas

**Files:**
- Create: `backend/app/schemas/book.py`

- [ ] **Step 1: Write `book.py`**

Create `backend/app/schemas/book.py`:

```python
from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class BookBase(BaseModel):
    isbn: str | None = Field(default=None, max_length=20)
    title: str = Field(..., min_length=1, max_length=256)
    author: str | None = Field(default=None, max_length=256)
    publisher: str | None = Field(default=None, max_length=128)
    category: str | None = Field(default=None, max_length=32)
    location: str | None = Field(default=None, max_length=64)
    total_copies: int = Field(default=1, ge=1)
    available_copies: int = Field(default=1, ge=0)
    metadata: dict[str, Any] = Field(default_factory=dict)


class BookCreate(BookBase):
    pass


class BookUpdate(BaseModel):
    title: str | None = None
    author: str | None = None
    publisher: str | None = None
    category: str | None = None
    location: str | None = None
    total_copies: int | None = Field(default=None, ge=1)
    available_copies: int | None = Field(default=None, ge=0)
    metadata: dict[str, Any] | None = None


class BookResponse(BookBase):
    id: int
    status: str
    created_at: datetime
    updated_at: datetime


class BookSearchHit(BaseModel):
    """One book hit returned by RAG-augmented search."""
    book: BookResponse
    score: float
    snippet: str | None = None
```

- [ ] **Step 2: Commit**

```bash
git add backend/app/schemas/book.py
git commit -m "feat(schemas): book request/response schemas"
```

---

### Task 17: Book repository

**Files:**
- Create: `backend/app/repositories/book_repository.py`

- [ ] **Step 1: Write `book_repository.py`**

Create `backend/app/repositories/book_repository.py`:

```python
from __future__ import annotations

from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Book


class BookRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def get_by_id(self, book_id: int, tenant_id: UUID) -> Book | None:
        stmt = select(Book).where(Book.id == book_id, Book.tenant_id == tenant_id)
        return (await self.session.execute(stmt)).scalar_one_or_none()

    async def list(
        self,
        tenant_id: UUID,
        *,
        category: str | None = None,
        q: str | None = None,
        page: int = 1,
        page_size: int = 20,
    ) -> tuple[list[Book], int]:
        stmt = select(Book).where(Book.tenant_id == tenant_id)
        count_stmt = select(func.count()).select_from(Book).where(Book.tenant_id == tenant_id)
        if category:
            stmt = stmt.where(Book.category == category)
            count_stmt = count_stmt.where(Book.category == category)
        if q:
            like = f"%{q}%"
            stmt = stmt.where((Book.title.ilike(like)) | (Book.author.ilike(like)))
            count_stmt = count_stmt.where((Book.title.ilike(like)) | (Book.author.ilike(like)))
        stmt = stmt.order_by(Book.id).offset((page - 1) * page_size).limit(page_size)
        items = (await self.session.execute(stmt)).scalars().all()
        total = (await self.session.execute(count_stmt)).scalar_one()
        return list(items), int(total)

    async def create(self, *, tenant_id: UUID, data: dict) -> Book:
        book = Book(tenant_id=tenant_id, **data)
        self.session.add(book)
        await self.session.flush()
        await self.session.refresh(book)
        return book

    async def update(self, book: Book, data: dict) -> Book:
        for k, v in data.items():
            if v is not None:
                setattr(book, k, v)
        await self.session.flush()
        await self.session.refresh(book)
        return book

    async def delete(self, book: Book) -> None:
        await self.session.delete(book)
        await self.session.flush()
```

- [ ] **Step 2: Verify import**

```bash
cd backend && uv run python -c "from app.repositories.book_repository import BookRepository; print('OK')"
```
Expected: `OK`

- [ ] **Step 3: Commit**

```bash
git add backend/app/repositories/book_repository.py
git commit -m "feat(repositories): BookRepository (CRUD + paginated list + search)"
```

---

### Task 18: Book service

**Files:**
- Create: `backend/app/services/book_service.py`

- [ ] **Step 1: Write `book_service.py`**

Create `backend/app/services/book_service.py`:

```python
from __future__ import annotations

from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import Conflict, NotFound
from app.models import Book
from app.repositories.book_repository import BookRepository


class BookService:
    def __init__(self, session: AsyncSession):
        self.session = session
        self.repo = BookRepository(session)

    async def list(
        self,
        tenant_id: UUID,
        *,
        category: str | None = None,
        q: str | None = None,
        page: int = 1,
        page_size: int = 20,
    ) -> tuple[list[Book], int]:
        return await self.repo.list(
            tenant_id, category=category, q=q, page=page, page_size=page_size
        )

    async def get(self, book_id: int, tenant_id: UUID) -> Book:
        book = await self.repo.get_by_id(book_id, tenant_id)
        if book is None:
            raise NotFound(f"Book {book_id} not found")
        return book

    async def create(self, *, tenant_id: UUID, data: dict) -> Book:
        if data.get("available_copies", 1) > data.get("total_copies", 1):
            raise Conflict("available_copies cannot exceed total_copies")
        return await self.repo.create(tenant_id=tenant_id, data=data)

    async def update(self, book_id: int, tenant_id: UUID, data: dict) -> Book:
        book = await self.get(book_id, tenant_id)
        new_total = data.get("total_copies", book.total_copies)
        new_avail = data.get("available_copies", book.available_copies)
        if new_avail > new_total:
            raise Conflict("available_copies cannot exceed total_copies")
        return await self.repo.update(book, data)

    async def delete(self, book_id: int, tenant_id: UUID) -> None:
        book = await self.get(book_id, tenant_id)
        await self.repo.delete(book)
```

- [ ] **Step 2: Verify import**

```bash
cd backend && uv run python -c "from app.services.book_service import BookService; print('OK')"
```
Expected: `OK`

- [ ] **Step 3: Commit**

```bash
git add backend/app/services/book_service.py
git commit -m "feat(services): BookService (CRUD with copies validation)"
```

---

### Task 19: Books API endpoints

**Files:**
- Create: `backend/app/api/v1/books.py`
- Modify: `backend/app/api/v1/router.py`

- [ ] **Step 1: Write `books.py`**

Create `backend/app/api/v1/books.py`:

```python
from __future__ import annotations

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Query, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, get_db
from app.core.exceptions import Forbidden
from app.models import User
from app.schemas.book import BookCreate, BookResponse, BookUpdate
from app.schemas.pagination import Page, PageRequest
from app.services.book_service import BookService

router = APIRouter(prefix="/books", tags=["books"])


def _require_librarian(user: User) -> None:
    if user.role not in ("librarian", "admin"):
        raise Forbidden("Librarian role required")


@router.get("", response_model=Page[BookResponse])
async def list_books(
    request: Request,
    db: Annotated[AsyncSession, Depends(get_db)],
    _: Annotated[User, Depends(get_current_user)],
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    category: str | None = None,
    q: str | None = None,
) -> Page[BookResponse]:
    tenant_id: UUID = request.state.tenant_id
    service = BookService(db)
    items, total = await service.list(
        tenant_id, category=category, q=q, page=page, page_size=page_size
    )
    return Page[BookResponse](
        items=[BookResponse.model_validate(b) for b in items],
        page=page,
        page_size=page_size,
        total=total,
    )


@router.get("/{book_id}", response_model=BookResponse)
async def get_book(
    request: Request,
    book_id: int,
    db: Annotated[AsyncSession, Depends(get_db)],
    _: Annotated[User, Depends(get_current_user)],
) -> BookResponse:
    tenant_id: UUID = request.state.tenant_id
    service = BookService(db)
    book = await service.get(book_id, tenant_id)
    return BookResponse.model_validate(book)


@router.post("", response_model=BookResponse, status_code=201)
async def create_book(
    request: Request,
    payload: BookCreate,
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[User, Depends(get_current_user)],
) -> BookResponse:
    _require_librarian(user)
    tenant_id: UUID = request.state.tenant_id
    service = BookService(db)
    book = await service.create(
        tenant_id=tenant_id,
        data=payload.model_dump(),
    )
    return BookResponse.model_validate(book)


@router.patch("/{book_id}", response_model=BookResponse)
async def update_book(
    request: Request,
    book_id: int,
    payload: BookUpdate,
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[User, Depends(get_current_user)],
) -> BookResponse:
    _require_librarian(user)
    tenant_id: UUID = request.state.tenant_id
    service = BookService(db)
    book = await service.update(book_id, tenant_id, payload.model_dump(exclude_unset=True))
    return BookResponse.model_validate(book)


@router.delete("/{book_id}", status_code=204)
async def delete_book(
    request: Request,
    book_id: int,
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[User, Depends(get_current_user)],
) -> None:
    _require_librarian(user)
    tenant_id: UUID = request.state.tenant_id
    service = BookService(db)
    await service.delete(book_id, tenant_id)
```

- [ ] **Step 2: Wire router**

Modify `backend/app/api/v1/router.py`:

```python
from __future__ import annotations

from fastapi import APIRouter

from app.api.v1.auth import router as auth_router
from app.api.v1.books import router as books_router
from app.api.v1.health import router as health_router

api_router = APIRouter(prefix="/api/v1")
api_router.include_router(auth_router)
api_router.include_router(books_router)
api_router.include_router(health_router)
```

- [ ] **Step 3: Verify routes**

```bash
cd backend && uv run python -c "
from app.main import app
spec = app.openapi()
for path in sorted(spec['paths'].keys()):
    if 'books' in path:
        for method in spec['paths'][path]:
            print(f'{method.upper():7s} {path}')
"
```
Expected: 5 routes — GET/POST `/api/v1/books`, GET/PATCH/DELETE `/api/v1/books/{id}`

- [ ] **Step 4: Commit**

```bash
git add backend/app/api/v1/books.py backend/app/api/v1/router.py
git commit -m "feat(api): books endpoints (list/get/create/update/delete, librarian-only writes)"
```

---

## Phase 7: Seat + Appointment Service + Endpoints

### Task 20: Seat repository

**Files:**
- Create: `backend/app/repositories/seat_repository.py`

- [ ] **Step 1: Write `seat_repository.py`**

Create `backend/app/repositories/seat_repository.py`:

```python
from __future__ import annotations

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Seat


class SeatRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def get_by_id(self, seat_id: int, tenant_id: UUID) -> Seat | None:
        stmt = select(Seat).where(Seat.id == seat_id, Seat.tenant_id == tenant_id)
        return (await self.session.execute(stmt)).scalar_one_or_none()

    async def list_all(self, tenant_id: UUID) -> list[Seat]:
        stmt = select(Seat).where(Seat.tenant_id == tenant_id).order_by(Seat.floor, Seat.code)
        return list((await self.session.execute(stmt)).scalars().all())

    async def list_by_floor(self, tenant_id: UUID, floor: str) -> list[Seat]:
        stmt = (
            select(Seat)
            .where(Seat.tenant_id == tenant_id, Seat.floor == floor)
            .order_by(Seat.code)
        )
        return list((await self.session.execute(stmt)).scalars().all())
```

- [ ] **Step 2: Commit**

```bash
git add backend/app/repositories/seat_repository.py
git commit -m "feat(repositories): SeatRepository"
```

---

### Task 21: Appointment repository (with optimistic lock)

**Files:**
- Create: `backend/app/repositories/appointment_repository.py`

- [ ] **Step 1: Write `appointment_repository.py`**

Create `backend/app/repositories/appointment_repository.py`:

```python
from __future__ import annotations

from datetime import datetime
from uuid import UUID

from sqlalchemy import and_, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Appointment, AppointmentStatus


class AppointmentRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def list_for_user(self, user_id: int, tenant_id: UUID) -> list[Appointment]:
        stmt = (
            select(Appointment)
            .where(Appointment.user_id == user_id, Appointment.tenant_id == tenant_id)
            .order_by(Appointment.start_time.desc())
        )
        return list((await self.session.execute(stmt)).scalars().all())

    async def get_by_id(self, appt_id: int, tenant_id: UUID) -> Appointment | None:
        stmt = select(Appointment).where(
            Appointment.id == appt_id, Appointment.tenant_id == tenant_id
        )
        return (await self.session.execute(stmt)).scalar_one_or_none()

    async def check_time_conflict(
        self,
        tenant_id: UUID,
        seat_id: int,
        start_time: datetime,
        end_time: datetime,
    ) -> bool:
        """Return True if any non-cancelled appointment overlaps the window for this seat."""
        stmt = select(Appointment.id).where(
            and_(
                Appointment.tenant_id == tenant_id,
                Appointment.seat_id == seat_id,
                Appointment.status.in_(
                    [AppointmentStatus.pending.value, AppointmentStatus.confirmed.value, AppointmentStatus.active.value]
                ),
                Appointment.start_time < end_time,
                Appointment.end_time > start_time,
            )
        ).limit(1)
        return (await self.session.execute(stmt)).scalar_one_or_none() is not None

    async def create(
        self,
        *,
        tenant_id: UUID,
        user_id: int,
        seat_id: int,
        start_time: datetime,
        end_time: datetime,
    ) -> Appointment:
        appt = Appointment(
            tenant_id=tenant_id,
            user_id=user_id,
            resource_type="seat",
            resource_id=seat_id,
            seat_id=seat_id,
            start_time=start_time,
            end_time=end_time,
            status=AppointmentStatus.confirmed.value,
            version=0,
        )
        self.session.add(appt)
        await self.session.flush()
        await self.session.refresh(appt)
        return appt

    async def cancel_with_version(
        self,
        appt: Appointment,
        *,
        expected_version: int,
        reason: str | None = None,
    ) -> bool:
        """Optimistic-lock UPDATE; returns False if version mismatch."""
        now = datetime.utcnow()
        stmt = (
            update(Appointment)
            .where(Appointment.id == appt.id, Appointment.version == expected_version)
            .values(
                status=AppointmentStatus.cancelled.value,
                cancelled_at=now,
                cancel_reason=reason,
                version=expected_version + 1,
            )
        )
        result = await self.session.execute(stmt)
        return result.rowcount > 0
```

- [ ] **Step 2: Commit**

```bash
git add backend/app/repositories/appointment_repository.py
git commit -m "feat(repositories): AppointmentRepository (optimistic-lock cancel)"
```

---

### Task 22: Appointment service (Redis lock + PG version)

**Files:**
- Create: `backend/app/services/appointment_service.py`

- [ ] **Step 1: Write `appointment_service.py`**

Create `backend/app/services/appointment_service.py`:

```python
from __future__ import annotations

from datetime import datetime, timedelta
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.clients.redis_client import get_redis
from app.core.concurrency import DistributedLock, LockAcquireError, acquire_with_retry
from app.core.exceptions import Conflict, NotFound
from app.models import Appointment
from app.repositories.appointment_repository import AppointmentRepository
from app.repositories.seat_repository import SeatRepository


class AppointmentService:
    def __init__(self, session: AsyncSession):
        self.session = session
        self.repo = AppointmentRepository(session)
        self.seat_repo = SeatRepository(session)

    async def list_for_user(self, user_id: int, tenant_id: UUID) -> list[Appointment]:
        return await self.repo.list_for_user(user_id, tenant_id)

    async def get(self, appt_id: int, tenant_id: UUID) -> Appointment:
        appt = await self.repo.get_by_id(appt_id, tenant_id)
        if appt is None:
            raise NotFound(f"Appointment {appt_id} not found")
        return appt

    async def book_seat(
        self,
        *,
        tenant_id: UUID,
        user_id: int,
        seat_id: int,
        start_time: datetime,
        end_time: datetime,
    ) -> Appointment:
        # Validate seat exists
        seat = await self.seat_repo.get_by_id(seat_id, tenant_id)
        if seat is None:
            raise NotFound(f"Seat {seat_id} not found")
        if end_time <= start_time:
            raise Conflict("end_time must be after start_time")

        # Stage 1: Redis distributed lock on seat
        redis = get_redis()
        lock_key = f"lock:seat:{tenant_id}:{seat_id}"
        try:
            lock = await acquire_with_retry(
                lambda: DistributedLock(redis, key=lock_key, ttl_ms=3000),
                max_retries=3,
            )
        except LockAcquireError:
            raise Conflict("Seat is being booked by another user, please retry")

        try:
            # Stage 2: DB-level conflict check
            conflict = await self.repo.check_time_conflict(
                tenant_id, seat_id, start_time, end_time
            )
            if conflict:
                raise Conflict("Seat is already booked in this time slot")
            return await self.repo.create(
                tenant_id=tenant_id,
                user_id=user_id,
                seat_id=seat_id,
                start_time=start_time,
                end_time=end_time,
            )
        finally:
            await lock.__aexit__(None, None, None)

    async def cancel(
        self,
        appt_id: int,
        tenant_id: UUID,
        user_id: int,
        *,
        reason: str | None = None,
    ) -> Appointment:
        appt = await self.get(appt_id, tenant_id)
        if appt.user_id != user_id:
            raise Conflict("Cannot cancel another user's appointment")
        # Stage 1: Redis lock
        redis = get_redis()
        lock_key = f"lock:appt:{tenant_id}:{appt_id}"
        try:
            lock = await acquire_with_retry(
                lambda: DistributedLock(redis, key=lock_key, ttl_ms=3000),
                max_retries=3,
            )
        except LockAcquireError:
            raise Conflict("Appointment is being modified, please retry")
        try:
            # Stage 2: PG optimistic lock
            ok = await self.repo.cancel_with_version(
                appt, expected_version=appt.version, reason=reason
            )
            if not ok:
                raise Conflict("Appointment was modified concurrently, please retry")
            await self.session.refresh(appt)
            return appt
        finally:
            await lock.__aexit__(None, None, None)
```

- [ ] **Step 2: Verify import**

```bash
cd backend && uv run python -c "from app.services.appointment_service import AppointmentService; print('OK')"
```
Expected: `OK`

- [ ] **Step 3: Commit**

```bash
git add backend/app/services/appointment_service.py
git commit -m "feat(services): AppointmentService (Redis lock + PG version optimistic)"
```

---

### Task 23: Seat + Appointment schemas + endpoints

**Files:**
- Create: `backend/app/schemas/seat.py`
- Create: `backend/app/schemas/appointment.py`
- Create: `backend/app/api/v1/seats.py`
- Create: `backend/app/api/v1/appointments.py`
- Modify: `backend/app/api/v1/router.py`

- [ ] **Step 1: Write `seat.py` schema**

Create `backend/app/schemas/seat.py`:

```python
from __future__ import annotations

from pydantic import BaseModel


class SeatResponse(BaseModel):
    id: int
    code: str
    floor: str
    zone: str
    status: str
    has_power: bool
    has_monitor: bool
    coord_x: int
    coord_y: int


class SeatListResponse(BaseModel):
    items: list[SeatResponse]
    total: int
```

- [ ] **Step 2: Write `appointment.py` schema**

Create `backend/app/schemas/appointment.py`:

```python
from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field


class AppointmentCreate(BaseModel):
    seat_id: int = Field(..., ge=1)
    start_time: datetime
    end_time: datetime


class AppointmentResponse(BaseModel):
    id: int
    user_id: int
    seat_id: int | None
    start_time: datetime
    end_time: datetime
    status: str
    version: int


class AppointmentCancelRequest(BaseModel):
    reason: str | None = Field(default=None, max_length=128)
```

- [ ] **Step 3: Write `seats.py` API**

Create `backend/app/api/v1/seats.py`:

```python
from __future__ import annotations

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, get_db
from app.models import User
from app.repositories.seat_repository import SeatRepository
from app.schemas.seat import SeatListResponse, SeatResponse

router = APIRouter(prefix="/seats", tags=["seats"])


@router.get("", response_model=SeatListResponse)
async def list_seats(
    request: Request,
    db: Annotated[AsyncSession, Depends(get_db)],
    _: Annotated[User, Depends(get_current_user)],
) -> SeatListResponse:
    tenant_id: UUID = request.state.tenant_id
    repo = SeatRepository(db)
    items = await repo.list_all(tenant_id)
    return SeatListResponse(
        items=[SeatResponse.model_validate(s) for s in items],
        total=len(items),
    )


@router.get("/floor/{floor}", response_model=SeatListResponse)
async def list_seats_by_floor(
    floor: str,
    request: Request,
    db: Annotated[AsyncSession, Depends(get_db)],
    _: Annotated[User, Depends(get_current_user)],
) -> SeatListResponse:
    tenant_id: UUID = request.state.tenant_id
    repo = SeatRepository(db)
    items = await repo.list_by_floor(tenant_id, floor)
    return SeatListResponse(
        items=[SeatResponse.model_validate(s) for s in items],
        total=len(items),
    )


@router.get("/available", response_model=SeatListResponse)
async def list_available_seats(
    request: Request,
    db: Annotated[AsyncSession, Depends(get_db)],
    _: Annotated[User, Depends(get_current_user)],
) -> SeatListResponse:
    """Currently-available seats (status='available')."""
    tenant_id: UUID = request.state.tenant_id
    repo = SeatRepository(db)
    all_seats = await repo.list_all(tenant_id)
    available = [s for s in all_seats if s.status == "available"]
    return SeatListResponse(
        items=[SeatResponse.model_validate(s) for s in available],
        total=len(available),
    )
```

- [ ] **Step 4: Write `appointments.py` API**

Create `backend/app/api/v1/appointments.py`:

```python
from __future__ import annotations

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, get_db
from app.models import User
from app.schemas.appointment import (
    AppointmentCancelRequest,
    AppointmentCreate,
    AppointmentResponse,
)
from app.services.appointment_service import AppointmentService

router = APIRouter(prefix="/appointments", tags=["appointments"])


@router.get("", response_model=list[AppointmentResponse])
async def list_my_appointments(
    request: Request,
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[User, Depends(get_current_user)],
) -> list[AppointmentResponse]:
    tenant_id: UUID = request.state.tenant_id
    service = AppointmentService(db)
    items = await service.list_for_user(user.id, tenant_id)
    return [AppointmentResponse.model_validate(a) for a in items]


@router.get("/{appt_id}", response_model=AppointmentResponse)
async def get_appointment(
    appt_id: int,
    request: Request,
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[User, Depends(get_current_user)],
) -> AppointmentResponse:
    tenant_id: UUID = request.state.tenant_id
    service = AppointmentService(db)
    appt = await service.get(appt_id, tenant_id)
    if appt.user_id != user.id and user.role not in ("librarian", "admin"):
        from app.core.exceptions import Forbidden
        raise Forbidden("Cannot view another user's appointment")
    return AppointmentResponse.model_validate(appt)


@router.post("", response_model=AppointmentResponse, status_code=201)
async def book_seat(
    request: Request,
    payload: AppointmentCreate,
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[User, Depends(get_current_user)],
) -> AppointmentResponse:
    tenant_id: UUID = request.state.tenant_id
    service = AppointmentService(db)
    appt = await service.book_seat(
        tenant_id=tenant_id,
        user_id=user.id,
        seat_id=payload.seat_id,
        start_time=payload.start_time,
        end_time=payload.end_time,
    )
    return AppointmentResponse.model_validate(appt)


@router.post("/{appt_id}/cancel", response_model=AppointmentResponse)
async def cancel_appointment(
    appt_id: int,
    payload: AppointmentCancelRequest,
    request: Request,
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[User, Depends(get_current_user)],
) -> AppointmentResponse:
    tenant_id: UUID = request.state.tenant_id
    service = AppointmentService(db)
    appt = await service.cancel(appt_id, tenant_id, user.id, reason=payload.reason)
    return AppointmentResponse.model_validate(appt)
```

- [ ] **Step 5: Wire routers**

Replace `backend/app/api/v1/router.py`:

```python
from __future__ import annotations

from fastapi import APIRouter

from app.api.v1.appointments import router as appointments_router
from app.api.v1.auth import router as auth_router
from app.api.v1.books import router as books_router
from app.api.v1.health import router as health_router
from app.api.v1.seats import router as seats_router

api_router = APIRouter(prefix="/api/v1")
api_router.include_router(auth_router)
api_router.include_router(books_router)
api_router.include_router(seats_router)
api_router.include_router(appointments_router)
api_router.include_router(health_router)
```

- [ ] **Step 6: Verify all routes load**

```bash
cd backend && uv run python -c "
from app.main import app
spec = app.openapi()
for path in sorted(spec['paths'].keys()):
    for method in spec['paths'][path]:
        print(f'{method.upper():7s} {path}')
" | wc -l
```
Expected: ~15 routes total

- [ ] **Step 7: Commit**

```bash
git add backend/app/schemas/seat.py backend/app/schemas/appointment.py backend/app/api/v1/seats.py backend/app/api/v1/appointments.py backend/app/api/v1/router.py
git commit -m "feat(api): seats + appointments endpoints with two-layer concurrency"
```

---

## Phase 8: Policy Service + Admin Endpoints

### Task 24: Policy schemas + repository + service

**Files:**
- Create: `backend/app/schemas/policy.py`
- Create: `backend/app/repositories/policy_repository.py`
- Create: `backend/app/services/policy_service.py`

- [ ] **Step 1: Write `policy.py` schema**

Create `backend/app/schemas/policy.py`:

```python
from __future__ import annotations

from datetime import date, datetime

from pydantic import BaseModel, Field


class PolicyBase(BaseModel):
    title: str = Field(..., min_length=1, max_length=256)
    content: str = Field(..., min_length=1)
    category: str | None = Field(default=None, max_length=32)
    effective_from: date | None = None
    effective_to: date | None = None


class PolicyCreate(PolicyBase):
    pass


class PolicyUpdate(BaseModel):
    title: str | None = None
    content: str | None = None
    category: str | None = None
    effective_from: date | None = None
    effective_to: date | None = None


class PolicyResponse(PolicyBase):
    id: int
    version: int
    indexed_at: datetime | None
    created_at: datetime
    updated_at: datetime
```

- [ ] **Step 2: Write `policy_repository.py`**

Create `backend/app/repositories/policy_repository.py`:

```python
from __future__ import annotations

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Policy


class PolicyRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def get_by_id(self, policy_id: int, tenant_id: UUID) -> Policy | None:
        stmt = select(Policy).where(Policy.id == policy_id, Policy.tenant_id == tenant_id)
        return (await self.session.execute(stmt)).scalar_one_or_none()

    async def list_all(self, tenant_id: UUID) -> list[Policy]:
        stmt = select(Policy).where(Policy.tenant_id == tenant_id).order_by(Policy.id)
        return list((await self.session.execute(stmt)).scalars().all())

    async def create(self, *, tenant_id: UUID, data: dict) -> Policy:
        policy = Policy(tenant_id=tenant_id, **data)
        self.session.add(policy)
        await self.session.flush()
        await self.session.refresh(policy)
        return policy

    async def update(self, policy: Policy, data: dict) -> Policy:
        for k, v in data.items():
            if v is not None:
                setattr(policy, k, v)
        policy.version += 1
        await self.session.flush()
        await self.session.refresh(policy)
        return policy

    async def delete(self, policy: Policy) -> None:
        await self.session.delete(policy)
        await self.session.flush()
```

- [ ] **Step 3: Write `policy_service.py` (with RAG indexing)**

Create `backend/app/services/policy_service.py`:

```python
from __future__ import annotations

from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import NotFound
from app.models import Policy
from app.rag.bm25_index import WhooshIndexManager
from app.rag.chroma_store import ChromaStore
from app.rag.chunker import chunk_text
from app.clients.embedding_client import EmbeddingClient
from app.repositories.policy_repository import PolicyRepository


class PolicyService:
    def __init__(
        self,
        session: AsyncSession,
        *,
        bm25: WhooshIndexManager,
        chroma: ChromaStore,
        embedding: EmbeddingClient,
    ):
        self.session = session
        self.repo = PolicyRepository(session)
        self.bm25 = bm25
        self.chroma = chroma
        self.embedding = embedding

    async def list_all(self, tenant_id: UUID) -> list[Policy]:
        return await self.repo.list_all(tenant_id)

    async def get(self, policy_id: int, tenant_id: UUID) -> Policy:
        policy = await self.repo.get_by_id(policy_id, tenant_id)
        if policy is None:
            raise NotFound(f"Policy {policy_id} not found")
        return policy

    async def create(self, *, tenant_id: UUID, data: dict) -> Policy:
        policy = await self.repo.create(tenant_id=tenant_id, data=data)
        await self._index_policy(tenant_id, policy)
        return policy

    async def update(self, policy_id: int, tenant_id: UUID, data: dict) -> Policy:
        policy = await self.get(policy_id, tenant_id)
        # Remove old chunks
        self._delete_index(tenant_id, str(policy.id))
        updated = await self.repo.update(policy, data)
        await self._index_policy(tenant_id, updated)
        return updated

    async def delete(self, policy_id: int, tenant_id: UUID) -> None:
        policy = await self.get(policy_id, tenant_id)
        self._delete_index(tenant_id, str(policy.id))
        await self.repo.delete(policy)

    async def reindex(self, policy_id: int, tenant_id: UUID) -> Policy:
        policy = await self.get(policy_id, tenant_id)
        self._delete_index(tenant_id, str(policy.id))
        await self._index_policy(tenant_id, policy)
        return policy

    async def _index_policy(self, tenant_id: UUID, policy: Policy) -> None:
        chunks = chunk_text(policy.content)
        if not chunks:
            return
        # BM25
        self.bm25.add_chunks(
            tenant_id,
            [(c.chunk_id, str(policy.id), policy.title, c.content) for c in chunks],
        )
        # ChromaDB (dense)
        vectors = await self.embedding.embed([c.content for c in chunks])
        self.chroma.upsert(
            tenant_id,
            ids=[c.chunk_id for c in chunks],
            embeddings=vectors,
            documents=[c.content for c in chunks],
            metadatas=[
                {"source_id": str(policy.id), "title": policy.title}
                for _ in chunks
            ],
        )
        # Mark indexed_at
        from datetime import datetime, timezone
        policy.indexed_at = datetime.now(timezone.utc)
        await self.session.flush()

    def _delete_index(self, tenant_id: UUID, source_id: str) -> None:
        self.bm25.delete_by_source(tenant_id, source_id)
        self.chroma.delete_by_source(tenant_id, source_id)
```

- [ ] **Step 4: Verify imports**

```bash
cd backend && uv run python -c "
from app.schemas.policy import PolicyCreate, PolicyResponse
from app.repositories.policy_repository import PolicyRepository
from app.services.policy_service import PolicyService
print('OK')
"
```
Expected: `OK`

- [ ] **Step 5: Commit**

```bash
git add backend/app/schemas/policy.py backend/app/repositories/policy_repository.py backend/app/services/policy_service.py
git commit -m "feat(policies): schemas + repo + service with RAG indexing (BM25+ChromaDB)"
```

---

### Task 25: Admin policy endpoints

**Files:**
- Create: `backend/app/api/v1/admin_policies.py`
- Modify: `backend/app/api/v1/router.py`

- [ ] **Step 1: Write `admin_policies.py`**

Create `backend/app/api/v1/admin_policies.py`:

```python
from __future__ import annotations

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, get_db
from app.clients.embedding_client import EmbeddingClient
from app.core.exceptions import Forbidden
from app.models import User
from app.rag.bm25_index import WhooshIndexManager
from app.rag.chroma_store import ChromaStore
from app.schemas.policy import PolicyCreate, PolicyResponse, PolicyUpdate
from app.services.policy_service import PolicyService

router = APIRouter(prefix="/admin/policies", tags=["admin"])


def _require_librarian(user: User) -> None:
    if user.role not in ("librarian", "admin"):
        raise Forbidden("Librarian role required")


def _get_rag_deps(request: Request) -> tuple[WhooshIndexManager, ChromaStore, EmbeddingClient]:
    """Pull RAG singletons from app.state (initialized in lifespan)."""
    return (
        request.app.state.bm25_index,
        request.app.state.chroma_store,
        request.app.state.embedding_client,
    )


@router.get("", response_model=list[PolicyResponse])
async def list_policies(
    request: Request,
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[User, Depends(get_current_user)],
) -> list[PolicyResponse]:
    _require_librarian(user)
    tenant_id: UUID = request.state.tenant_id
    bm25, chroma, emb = _get_rag_deps(request)
    service = PolicyService(db, bm25=bm25, chroma=chroma, embedding=emb)
    items = await service.list_all(tenant_id)
    return [PolicyResponse.model_validate(p) for p in items]


@router.post("", response_model=PolicyResponse, status_code=201)
async def create_policy(
    request: Request,
    payload: PolicyCreate,
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[User, Depends(get_current_user)],
) -> PolicyResponse:
    _require_librarian(user)
    tenant_id: UUID = request.state.tenant_id
    bm25, chroma, emb = _get_rag_deps(request)
    service = PolicyService(db, bm25=bm25, chroma=chroma, embedding=emb)
    policy = await service.create(tenant_id=tenant_id, data=payload.model_dump())
    return PolicyResponse.model_validate(policy)


@router.patch("/{policy_id}", response_model=PolicyResponse)
async def update_policy(
    policy_id: int,
    payload: PolicyUpdate,
    request: Request,
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[User, Depends(get_current_user)],
) -> PolicyResponse:
    _require_librarian(user)
    tenant_id: UUID = request.state.tenant_id
    bm25, chroma, emb = _get_rag_deps(request)
    service = PolicyService(db, bm25=bm25, chroma=chroma, embedding=emb)
    policy = await service.update(policy_id, tenant_id, payload.model_dump(exclude_unset=True))
    return PolicyResponse.model_validate(policy)


@router.delete("/{policy_id}", status_code=204)
async def delete_policy(
    policy_id: int,
    request: Request,
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[User, Depends(get_current_user)],
) -> None:
    if user.role != "admin":
        raise Forbidden("Admin role required")
    tenant_id: UUID = request.state.tenant_id
    bm25, chroma, emb = _get_rag_deps(request)
    service = PolicyService(db, bm25=bm25, chroma=chroma, embedding=emb)
    await service.delete(policy_id, tenant_id)


@router.post("/{policy_id}/reindex", response_model=PolicyResponse)
async def reindex_policy(
    policy_id: int,
    request: Request,
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[User, Depends(get_current_user)],
) -> PolicyResponse:
    if user.role != "admin":
        raise Forbidden("Admin role required")
    tenant_id: UUID = request.state.tenant_id
    bm25, chroma, emb = _get_rag_deps(request)
    service = PolicyService(db, bm25=bm25, chroma=chroma, embedding=emb)
    policy = await service.reindex(policy_id, tenant_id)
    return PolicyResponse.model_validate(policy)
```

- [ ] **Step 2: Wire router**

Replace `backend/app/api/v1/router.py`:

```python
from __future__ import annotations

from fastapi import APIRouter

from app.api.v1.admin_policies import router as admin_policies_router
from app.api.v1.appointments import router as appointments_router
from app.api.v1.auth import router as auth_router
from app.api.v1.books import router as books_router
from app.api.v1.health import router as health_router
from app.api.v1.seats import router as seats_router

api_router = APIRouter(prefix="/api/v1")
api_router.include_router(auth_router)
api_router.include_router(books_router)
api_router.include_router(seats_router)
api_router.include_router(appointments_router)
api_router.include_router(admin_policies_router)
api_router.include_router(health_router)
```

- [ ] **Step 3: Wire RAG singletons into create_app**

Modify `backend/app/main.py` — add to top imports (after existing imports):

```python
from pathlib import Path

from app.clients.embedding_client import EmbeddingClient
from app.rag.bm25_index import WhooshIndexManager
from app.rag.chroma_store import ChromaStore
```

Replace `create_app` function body (keep the `lifespan` function unchanged):

```python
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
```

- [ ] **Step 4: Verify app still imports**

```bash
cd backend && uv run python -c "from app.main import app; print('OK')"
```
Expected: `OK`

- [ ] **Step 5: Commit**

```bash
git add backend/app/api/v1/admin_policies.py backend/app/api/v1/router.py backend/app/main.py
git commit -m "feat(api): admin policy endpoints + RAG singletons wired into app state"
```

---

## Phase 9: Integration Tests

### Task 26: Book API integration tests

**Files:**
- Create: `backend/tests/integration/test_books_api.py`

- [ ] **Step 1: Write the tests**

Create `backend/tests/integration/test_books_api.py`:

```python
from uuid import UUID

import pytest

pytestmark = pytest.mark.integration


async def _seed_tenant(db_session):
    from app.models import Tenant
    tid = UUID("00000000-0000-0000-0000-000000000001")
    existing = await db_session.get(Tenant, tid)
    if not existing:
        tenant = Tenant(id=tid, code="main_library", name="Main Library", status="active", config={})
        db_session.add(tenant)
        await db_session.commit()
    return tid


async def _register_user(client, student_no="2024001"):
    response = await client.post(
        "/api/v1/auth/register",
        json={"student_no": student_no, "password": "test_pass_123", "full_name": "Test"},
    )
    assert response.status_code == 201
    return response.json()["access_token"]


async def test_list_books_empty(client, db_session):
    await _seed_tenant(db_session)
    token = await _register_user(client)
    response = await client.get("/api/v1/books", headers={"Authorization": f"Bearer {token}"})
    assert response.status_code == 200
    data = response.json()
    assert data["items"] == []
    assert data["total"] == 0


async def test_create_book_requires_librarian(client, db_session):
    await _seed_tenant(db_session)
    token = await _register_user(client, student_no="2024002")  # student role
    response = await client.post(
        "/api/v1/books",
        headers={"Authorization": f"Bearer {token}"},
        json={"title": "Test Book", "author": "Author", "total_copies": 2},
    )
    assert response.status_code == 403


async def test_create_then_list_book(client, db_session):
    await _seed_tenant(db_session)
    token = await _register_user(client, student_no="2024003")
    # Need to upgrade to librarian role — directly via DB
    from app.models import User
    from sqlalchemy import select, update
    await db_session.execute(
        update(User).where(User.student_no == "2024003").values(role="librarian")
    )
    await db_session.commit()
    # Re-login to get fresh token with new role
    login = await client.post(
        "/api/v1/auth/login",
        json={"student_no": "2024003", "password": "test_pass_123"},
    )
    token = login.json()["access_token"]

    create = await client.post(
        "/api/v1/books",
        headers={"Authorization": f"Bearer {token}"},
        json={"title": "深入理解计算机系统", "author": "Bryant", "total_copies": 5},
    )
    assert create.status_code == 201, create.text
    book_id = create.json()["id"]

    listing = await client.get(
        "/api/v1/books",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert listing.status_code == 200
    assert listing.json()["total"] == 1
    assert listing.json()["items"][0]["id"] == book_id
```

- [ ] **Step 2: Run (will skip if no Docker)**

```bash
cd backend && uv run pytest tests/integration/test_books_api.py -v
```
Expected: errors with "Docker daemon not reachable" — code-level review is enough for now.

- [ ] **Step 3: Commit**

```bash
git add backend/tests/integration/test_books_api.py
git commit -m "test(integration): books API (list/create, librarian RBAC)"
```

---

### Task 27: Appointment booking flow test

**Files:**
- Create: `backend/tests/integration/test_appointments_api.py`

- [ ] **Step 1: Write the test**

Create `backend/tests/integration/test_appointments_api.py`:

```python
from datetime import datetime, timedelta, timezone
from uuid import UUID

import pytest

pytestmark = pytest.mark.integration


async def _seed_tenant(db_session):
    from app.models import Tenant
    tid = UUID("00000000-0000-0000-0000-000000000001")
    if not await db_session.get(Tenant, tid):
        tenant = Tenant(id=tid, code="main_library", name="Main", status="active", config={})
        db_session.add(tenant)
        await db_session.commit()


async def _register_student(client, student_no):
    r = await client.post(
        "/api/v1/auth/register",
        json={"student_no": student_no, "password": "test_pass_123", "full_name": student_no},
    )
    return r.json()["access_token"]


async def _create_seat(db_session, code="A-101"):
    from app.models import Seat
    seat = Seat(
        tenant_id=UUID("00000000-0000-0000-0000-000000000001"),
        code=code,
        floor="1F",
        zone="silent",
        status="available",
        has_power=True,
        has_monitor=False,
        coord_x=10,
        coord_y=20,
    )
    db_session.add(seat)
    await db_session.commit()
    await db_session.refresh(seat)
    return seat


async def test_book_seat_happy_path(client, db_session):
    await _seed_tenant(db_session)
    seat = await _create_seat(db_session, code="A-101")
    token = await _register_student(client, "2024100")
    start = datetime.now(timezone.utc).replace(microsecond=0) + timedelta(hours=1)
    end = start + timedelta(hours=2)

    response = await client.post(
        "/api/v1/appointments",
        headers={"Authorization": f"Bearer {token}"},
        json={"seat_id": seat.id, "start_time": start.isoformat(), "end_time": end.isoformat()},
    )
    assert response.status_code == 201, response.text
    assert response.json()["status"] == "confirmed"


async def test_book_seat_conflict_returns_409(client, db_session):
    await _seed_tenant(db_session)
    seat = await _create_seat(db_session, code="A-102")
    token1 = await _register_student(client, "2024101")
    token2 = await _register_student(client, "2024102")
    start = datetime.now(timezone.utc).replace(microsecond=0) + timedelta(hours=2)
    end = start + timedelta(hours=2)

    r1 = await client.post(
        "/api/v1/appointments",
        headers={"Authorization": f"Bearer {token1}"},
        json={"seat_id": seat.id, "start_time": start.isoformat(), "end_time": end.isoformat()},
    )
    assert r1.status_code == 201

    r2 = await client.post(
        "/api/v1/appointments",
        headers={"Authorization": f"Bearer {token2}"},
        json={"seat_id": seat.id, "start_time": start.isoformat(), "end_time": end.isoformat()},
    )
    assert r2.status_code == 409
    assert r2.json()["error"]["code"] == "conflict"
```

- [ ] **Step 2: Commit**

```bash
git add backend/tests/integration/test_appointments_api.py
git commit -m "test(integration): appointment booking + conflict flow"
```

---

### Task 28: Policy admin tests

**Files:**
- Create: `backend/tests/integration/test_policies_api.py`

- [ ] **Step 1: Write the tests**

Create `backend/tests/integration/test_policies_api.py`:

```python
from uuid import UUID

import pytest

pytestmark = pytest.mark.integration


async def _seed_tenant(db_session):
    from app.models import Tenant
    tid = UUID("00000000-0000-0000-0000-000000000001")
    if not await db_session.get(Tenant, tid):
        tenant = Tenant(id=tid, code="main_library", name="Main", status="active", config={})
        db_session.add(tenant)
        await db_session.commit()


async def _register_and_promote(client, db_session, student_no, role="librarian"):
    await client.post(
        "/api/v1/auth/register",
        json={"student_no": student_no, "password": "test_pass_123", "full_name": student_no},
    )
    from app.models import User
    from sqlalchemy import update
    await db_session.execute(
        update(User).where(User.student_no == student_no).values(role=role)
    )
    await db_session.commit()
    login = await client.post(
        "/api/v1/auth/login",
        json={"student_no": student_no, "password": "test_pass_123"},
    )
    return login.json()["access_token"]


async def test_create_policy_indexes_into_rag(client, db_session):
    await _seed_tenant(db_session)
    token = await _register_and_promote(client, db_session, "2024200", role="librarian")
    response = await client.post(
        "/api/v1/admin/policies",
        headers={"Authorization": f"Bearer {token}"},
        json={
            "title": "借阅规则",
            "content": "本科生最多借 10 本,期限 30 天。研究生最多借 20 本。",
            "category": "borrow",
        },
    )
    assert response.status_code == 201, response.text
    assert response.json()["indexed_at"] is not None


async def test_create_policy_requires_librarian(client, db_session):
    await _seed_tenant(db_session)
    token = await _register_and_promote(client, db_session, "2024201", role="student")
    response = await client.post(
        "/api/v1/admin/policies",
        headers={"Authorization": f"Bearer {token}"},
        json={"title": "X", "content": "Y"},
    )
    assert response.status_code == 403
```

- [ ] **Step 2: Commit**

```bash
git add backend/tests/integration/test_policies_api.py
git commit -m "test(integration): policy admin (create + RAG indexing, RBAC)"
```

---

## Phase 10: Final Verification

### Task 29: Run all unit tests + verify imports

- [ ] **Step 1: Run unit tests**

```bash
cd backend && uv run pytest tests/unit -v --cov=app --cov-fail-under=75
```
Expected: 22+ tests pass (15 from Plan 01 + 7 new), coverage ≥75%

- [ ] **Step 2: Verify all imports**

```bash
cd backend && uv run python -c "
from app.main import app
from app.rag.pipeline import HybridRetriever
from app.rag.bm25_index import WhooshIndexManager
from app.rag.chroma_store import ChromaStore
from app.rag.chunker import chunk_text
from app.rag.rrf import reciprocal_rank_fusion
from app.clients.embedding_client import EmbeddingClient
from app.clients.rerank_client import RerankClient
from app.clients.redis_client import init_redis
from app.core.concurrency import DistributedLock
from app.services.book_service import BookService
from app.services.appointment_service import AppointmentService
from app.services.policy_service import PolicyService
print('All Plan 02 imports OK')
spec = app.openapi()
print(f'Total routes: {sum(len(v) for v in spec[\"paths\"].values())}')
"
```
Expected: `All Plan 02 imports OK`, ~18 routes

- [ ] **Step 3: Commit any straggler updates**

```bash
cd .. && git status
# If clean, skip. If dirty, commit.
```

---

## Summary

**28 tasks across 10 phases:**
- Phase 1 (4 tasks): Redis + Distributed lock + retry + lifespan wire-up
- Phase 2 (2 tasks): Document loaders + chunker
- Phase 3 (2 tasks): Whoosh BM25 index + retriever
- Phase 4 (3 tasks): ChromaDB store + Embedding client + Dense retriever
- Phase 5 (3 tasks): RRF + Rerank client + Hybrid pipeline
- Phase 6 (5 tasks): Pagination + Book schemas/repo/service/API
- Phase 7 (4 tasks): Seat repo + Appointment repo/service (Redis+PG) + endpoints
- Phase 8 (2 tasks): Policy schemas/repo/service + admin endpoints + RAG singletons
- Phase 9 (3 tasks): Integration tests for books/appointments/policies
- Phase 10 (1 task): Final verification

**Out of scope for this plan (deferred):**
- LangGraph multi-agent (Plan 03)
- Chat endpoints + SSE streaming (Plan 03)
- MCP Server tools (Plan 04)
- Full OpenTelemetry instrumentation (Plan 04)
- Frontend (Plan 05)
- Celery timeout-release task (deferred to Plan 04)
- Ragas evaluation pipeline (Plan 05)
