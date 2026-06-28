# Library Service Plan 01 — Infrastructure Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the foundational infrastructure for the Library Intelligent Service: FastAPI app skeleton, PostgreSQL schema with all core tables, JWT authentication, Docker Compose dev environment, basic observability, and CI pipeline. After this plan completes, `docker compose up` brings up the API with `/api/v1/health` returning 200 and `/api/v1/auth/login` issuing real JWTs.

**Architecture:** Layered monolith in a single Python package (`app/`). Async-first: SQLAlchemy 2.0 async, asyncpg driver, async Redis. JWT auth via FastAPI dependency injection. SQLAlchemy models with `tenant_id` column on every business table to support future multi-tenant evolution. OpenTelemetry tracing initialized at app startup, exported to OTLP collector.

**Tech Stack:**
- Python 3.12, FastAPI 0.115+, SQLAlchemy 2.0 async, asyncpg, Alembic
- PostgreSQL 15, Redis 7 (later), pydantic-settings, python-jose, passlib[bcrypt]
- pytest, pytest-asyncio, httpx, testcontainers
- OpenTelemetry SDK + OTLP exporter
- Docker Compose v2

**Reference Spec:** `docs/superpowers/specs/2026-06-28-library-intelligent-service-design.md` (especially §3 Schema, §9 API, §11 Deployment)

**Working Directory:** This plan assumes work in the parent directory `D:\Agent-Project\deep_research_scaffold\`. The plan creates a new `backend/` subdirectory.

---

## File Structure

```
deep_research_scaffold/
├── backend/
│   ├── app/
│   │   ├── __init__.py
│   │   ├── main.py                       # FastAPI app entry + lifespan
│   │   ├── core/
│   │   │   ├── __init__.py
│   │   │   ├── config.py                 # Pydantic Settings
│   │   │   ├── database.py               # Async SQLAlchemy engine + session
│   │   │   ├── redis_client.py           # Stub for Plan 02
│   │   │   ├── security.py               # JWT + password hash
│   │   │   ├── exceptions.py             # Exception hierarchy
│   │   │   ├── observability.py          # OTel init
│   │   │   ├── logging_config.py         # structlog + trace_id
│   │   │   └── middleware/
│   │   │       ├── __init__.py
│   │   │       ├── auth.py               # JWT extraction
│   │   │       └── tenant.py             # tenant_id injection
│   │   ├── api/
│   │   │   ├── __init__.py
│   │   │   ├── deps.py                   # FastAPI dependencies
│   │   │   └── v1/
│   │   │       ├── __init__.py
│   │   │       ├── router.py             # Aggregator
│   │   │       ├── health.py             # /health endpoint
│   │   │       └── auth.py               # /auth/register /login /refresh /me
│   │   ├── schemas/
│   │   │   ├── __init__.py
│   │   │   ├── auth.py
│   │   │   └── common.py                 # Error response schema
│   │   ├── models/
│   │   │   ├── __init__.py
│   │   │   ├── base.py                   # Base + TenantScopedMixin + TimestampMixin
│   │   │   ├── tenant.py
│   │   │   ├── user.py
│   │   │   ├── book.py
│   │   │   ├── seat.py
│   │   │   ├── appointment.py
│   │   │   ├── policy.py
│   │   │   └── enums.py                  # All enum types
│   │   ├── repositories/
│   │   │   ├── __init__.py
│   │   │   └── user_repository.py
│   │   └── services/
│   │       ├── __init__.py
│   │       └── user_service.py
│   ├── alembic/
│   │   ├── env.py
│   │   ├── script.py.mako
│   │   └── versions/
│   │       └── 0001_initial.py           # Auto-generated
│   ├── tests/
│   │   ├── __init__.py
│   │   ├── conftest.py
│   │   ├── unit/
│   │   │   ├── __init__.py
│   │   │   ├── test_security.py
│   │   │   ├── test_password.py
│   │   │   └── test_exceptions.py
│   │   └── integration/
│   │       ├── __init__.py
│   │       ├── test_health.py
│   │       └── test_auth_api.py
│   ├── pyproject.toml
│   ├── alembic.ini
│   ├── .env.example
│   ├── Dockerfile
│   └── requirements.txt
├── deploy/
│   ├── docker-compose.yml
│   ├── docker-compose.dev.yml
│   └── postgres/init.sql
├── .github/
│   └── workflows/
│       └── ci.yml
├── .gitignore
└── README.md
```

---

## Phase 1: Project Bootstrap

### Task 1: Initialize git repo and .gitignore

**Files:**
- Create: `.gitignore`

- [ ] **Step 1: Check if git is initialized**

Run: `cd /d/Agent-Project/deep_research_scaffold && git status 2>&1 || echo "not a git repo"`

Expected: either git status output OR `not a git repo`

- [ ] **Step 2: Initialize git repo (if not already)**

If the previous step showed `not a git repo`, run:
```bash
cd /d/Agent-Project/deep_research_scaffold
git init
git config user.email "dev@example.com"
git config user.name "Developer"
```

- [ ] **Step 3: Write .gitignore**

Create `D:\Agent-Project\deep_research_scaffold\.gitignore`:
```gitignore
# Python
__pycache__/
*.py[cod]
*$py.class
*.so
.Python
.venv/
venv/
env/
.env
.env.local
.env.*.local

# Distribution / packaging
build/
dist/
*.egg-info/
*.egg
.pytest_cache/
.ruff_cache/
.mypy_cache/
.coverage
htmlcov/
coverage.xml

# IDEs
.vscode/
.idea/
*.swp
*.swo
.DS_Store

# Docker
.docker/

# Logs
*.log

# Test artifacts
tests/artifacts/
```

- [ ] **Step 4: First commit**

```bash
git add .gitignore
git commit -m "chore: initialize git repo with .gitignore"
```

---

### Task 2: Create backend pyproject.toml with dependencies

**Files:**
- Create: `backend/pyproject.toml`
- Create: `backend/requirements.txt`

- [ ] **Step 1: Write requirements.txt**

Create `D:\Agent-Project\deep_research_scaffold\backend\requirements.txt`:
```
# Web framework
fastapi>=0.115.0
uvicorn[standard]>=0.30.0

# Database
sqlalchemy[asyncio]>=2.0.30
asyncpg>=0.29.0
alembic>=1.13.0

# Settings & validation
pydantic>=2.8.0
pydantic-settings>=2.4.0

# Auth
python-jose[cryptography]>=3.3.0
passlib[bcrypt]>=1.7.4
bcrypt==4.0.1

# Logging
structlog>=24.1.0

# Observability
opentelemetry-api>=1.27.0
opentelemetry-sdk>=1.27.0
opentelemetry-instrumentation-fastapi>=0.48b0
opentelemetry-instrumentation-sqlalchemy>=0.48b0
opentelemetry-exporter-otlp-proto-grpc>=1.27.0

# HTTP client (for tests)
httpx>=0.27.0

# Dev / test
pytest>=8.3.0
pytest-asyncio>=0.24.0
pytest-cov>=5.0.0
testcontainers[postgres]>=4.8.0
ruff>=0.5.0
mypy>=1.11.0
```

- [ ] **Step 2: Write pyproject.toml**

Create `D:\Agent-Project\deep_research_scaffold\backend\pyproject.toml`:
```toml
[project]
name = "library-service"
version = "0.1.0"
description = "Library Intelligent Service backend"
requires-python = ">=3.12"
readme = "README.md"

[tool.pytest.ini_options]
asyncio_mode = "auto"
testpaths = ["tests"]
addopts = "-v --tb=short --strict-markers"
markers = [
    "integration: marks tests as integration (deselect with '-m \"not integration\"')",
]

[tool.coverage.run]
source = ["app"]
omit = ["*/migrations/*", "*/tests/*", "*/alembic/*"]

[tool.coverage.report]
fail_under = 75
exclude_lines = [
    "pragma: no cover",
    "raise NotImplementedError",
    "if __name__ == .__main__.:",
]

[tool.ruff]
line-length = 110
target-version = "py312"

[tool.ruff.lint]
select = ["E", "F", "I", "B", "UP", "N", "C4"]
ignore = ["E501"]

[tool.mypy]
python_version = "3.12"
strict = true
files = ["app"]
ignore_missing_imports = true
```

- [ ] **Step 3: Install dependencies**

```bash
cd /d/Agent-Project/deep_research_scaffold/backend
python -m venv .venv
source .venv/bin/activate  # Git Bash on Windows; use .venv\Scripts\activate for PowerShell
pip install -r requirements.txt
```

Expected: All packages install successfully, exit 0.

- [ ] **Step 4: Verify FastAPI is importable**

```bash
python -c "import fastapi; print(fastapi.__version__)"
```

Expected: prints a version like `0.115.6`

- [ ] **Step 5: Commit**

```bash
cd /d/Agent-Project/deep_research_scaffold
git add backend/requirements.txt backend/pyproject.toml
git commit -m "chore: add backend dependencies and pyproject.toml"
```

---

### Task 3: Create backend package skeleton

**Files:**
- Create: `backend/app/__init__.py`
- Create: `backend/app/core/__init__.py`
- Create: `backend/app/api/__init__.py`
- Create: `backend/app/api/v1/__init__.py`
- Create: `backend/app/core/middleware/__init__.py`
- Create: `backend/app/schemas/__init__.py`
- Create: `backend/app/models/__init__.py`
- Create: `backend/app/repositories/__init__.py`
- Create: `backend/app/services/__init__.py`
- Create: `backend/tests/__init__.py`
- Create: `backend/tests/unit/__init__.py`
- Create: `backend/tests/integration/__init__.py`

- [ ] **Step 1: Create all __init__.py files**

Run from `D:\Agent-Project\deep_research_scaffold\`:
```bash
cd backend
touch app/__init__.py
touch app/core/__init__.py
touch app/api/__init__.py
touch app/api/v1/__init__.py
touch app/core/middleware/__init__.py
touch app/schemas/__init__.py
touch app/models/__init__.py
touch app/repositories/__init__.py
touch app/services/__init__.py
touch tests/__init__.py
touch tests/unit/__init__.py
touch tests/integration/__init__.py
```

On Windows cmd, use `type nul > file.py` instead of `touch`.

- [ ] **Step 2: Verify package imports**

```bash
cd /d/Agent-Project/deep_research_scaffold/backend
python -c "from app import core, api, schemas, models, repositories, services; print('OK')"
```

Expected: `OK`

- [ ] **Step 3: Commit**

```bash
cd /d/Agent-Project/deep_research_scaffold
git add backend/app backend/tests
git commit -m "chore: create backend package skeleton"
```

---

## Phase 2: Configuration

### Task 4: Pydantic Settings module

**Files:**
- Create: `backend/app/core/config.py`
- Test: `backend/tests/unit/test_config.py`

- [ ] **Step 1: Write the failing test**

Create `D:\Agent-Project\deep_research_scaffold\backend\tests\unit\test_config.py`:
```python
import pytest
from pydantic import ValidationError

from app.core.config import Settings


def test_settings_load_defaults(monkeypatch):
    monkeypatch.delenv("APP_ENV", raising=False)
    monkeypatch.delenv("POSTGRES_PASSWORD", raising=False)
    monkeypatch.delenv("JWT_SECRET", raising=False)
    settings = Settings()
    assert settings.app_env == "development"
    assert settings.database_url.startswith("postgresql+asyncpg://")
    assert settings.jwt_algorithm == "HS256"
    assert settings.jwt_access_ttl_seconds == 3600


def test_settings_override_from_env(monkeypatch):
    monkeypatch.setenv("APP_ENV", "production")
    monkeypatch.setenv("POSTGRES_PASSWORD", "secret123")
    monkeypatch.setenv("JWT_SECRET", "x" * 32)
    settings = Settings()
    assert settings.app_env == "production"
    assert "secret123" in settings.database_url


def test_settings_database_url_async(monkeypatch):
    monkeypatch.setenv("POSTGRES_PASSWORD", "x")
    monkeypatch.setenv("JWT_SECRET", "y" * 32)
    settings = Settings()
    assert settings.database_url.startswith("postgresql+asyncpg://")
    assert settings.database_url_sync.startswith("postgresql://")


def test_settings_invalid_env_raises(monkeypatch):
    monkeypatch.setenv("APP_ENV", "invalid_env_value")
    with pytest.raises(ValidationError):
        Settings()
```

- [ ] **Step 2: Run test to verify it fails**

```bash
cd /d/Agent-Project/deep_research_scaffold/backend
pytest tests/unit/test_config.py -v
```

Expected: FAIL with `ModuleNotFoundError: No module named 'app.core.config'`

- [ ] **Step 3: Write Settings implementation**

Create `D:\Agent-Project\deep_research_scaffold\backend\app\core\config.py`:
```python
from __future__ import annotations

from functools import lru_cache
from typing import Literal

from pydantic import Field, computed_field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment variables and .env file."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # App
    app_name: str = "Library Intelligent Service"
    app_version: str = "0.1.0"
    app_env: Literal["development", "staging", "production", "test"] = "development"
    log_level: str = "INFO"
    trace_sample_ratio: float = 1.0  # 100% in dev; lower in prod

    # Database
    postgres_host: str = "localhost"
    postgres_port: int = 5432
    postgres_user: str = "library"
    postgres_db: str = "library"
    postgres_password: str = Field(default="dev_password", min_length=1)

    # Redis (placeholder for Plan 02)
    redis_url: str = "redis://localhost:6379/0"

    # JWT
    jwt_secret: str = Field(default="dev_secret_minimum_32_characters_long_xx", min_length=32)
    jwt_algorithm: str = "HS256"
    jwt_access_ttl_seconds: int = 3600
    jwt_refresh_ttl_seconds: int = 60 * 60 * 24 * 30  # 30 days

    # Default tenant
    default_tenant_code: str = "main_library"

    # CORS
    cors_origins: list[str] = ["http://localhost:5173", "http://localhost:8000"]

    # OTel
    otel_collector_endpoint: str = "http://localhost:4317"
    otel_service_name: str = "library-service"

    @computed_field  # type: ignore[prop-decorator]
    @property
    def database_url(self) -> str:
        """Async database URL for SQLAlchemy + asyncpg."""
        return (
            f"postgresql+asyncpg://{self.postgres_user}:{self.postgres_password}"
            f"@{self.postgres_host}:{self.postgres_port}/{self.postgres_db}"
        )

    @computed_field  # type: ignore[prop-decorator]
    @property
    def database_url_sync(self) -> str:
        """Sync database URL for Alembic."""
        return (
            f"postgresql://{self.postgres_user}:{self.postgres_password}"
            f"@{self.postgres_host}:{self.postgres_port}/{self.postgres_db}"
        )


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
```

- [ ] **Step 4: Run test to verify it passes**

```bash
cd /d/Agent-Project/deep_research_scaffold/backend
pytest tests/unit/test_config.py -v
```

Expected: 4 tests pass

- [ ] **Step 5: Write .env.example**

Create `D:\Agent-Project\deep_research_scaffold\backend\.env.example`:
```bash
APP_ENV=development
LOG_LEVEL=INFO
TRACE_SAMPLE_RATIO=1.0

POSTGRES_HOST=localhost
POSTGRES_PORT=5432
POSTGRES_USER=library
POSTGRES_DB=library
POSTGRES_PASSWORD=dev_password

REDIS_URL=redis://localhost:6379/0

JWT_SECRET=dev_secret_minimum_32_characters_long_xx
JWT_ALGORITHM=HS256
JWT_ACCESS_TTL_SECONDS=3600
JWT_REFRESH_TTL_SECONDS=2592000

DEFAULT_TENANT_CODE=main_library

CORS_ORIGINS=["http://localhost:5173"]

OTEL_COLLECTOR_ENDPOINT=http://localhost:4317
OTEL_SERVICE_NAME=library-service
```

- [ ] **Step 6: Commit**

```bash
cd /d/Agent-Project/deep_research_scaffold
git add backend/app/core/config.py backend/tests/unit/test_config.py backend/.env.example
git commit -m "feat(config): add Pydantic Settings with env override"
```

---

## Phase 3: Exception Hierarchy

### Task 5: Exception classes

**Files:**
- Create: `backend/app/core/exceptions.py`
- Test: `backend/tests/unit/test_exceptions.py`

- [ ] **Step 1: Write the failing test**

Create `D:\Agent-Project\deep_research_scaffold\backend\tests\unit\test_exceptions.py`:
```python
from app.core.exceptions import (
    Conflict,
    LibraryBaseError,
    NotFound,
    Unauthorized,
    ValidationError,
)


def test_base_error_defaults():
    err = LibraryBaseError()
    assert err.code == "internal_error"
    assert err.status_code == 500


def test_unauthorized_inherits():
    err = Unauthorized("Token expired")
    assert err.status_code == 401
    assert err.code == "unauthorized"
    assert str(err) == "Token expired"


def test_conflict_carries_details():
    err = Conflict("Seat booked", details={"seat_id": 123})
    assert err.status_code == 409
    assert err.details == {"seat_id": 123}


def test_validation_error_is_client_error():
    err = ValidationError("Bad input")
    assert err.status_code == 422


def test_not_found():
    err = NotFound("Book not found")
    assert err.status_code == 404
    assert err.code == "not_found"
```

- [ ] **Step 2: Run test to verify it fails**

```bash
cd /d/Agent-Project/deep_research_scaffold/backend
pytest tests/unit/test_exceptions.py -v
```

Expected: FAIL with `ModuleNotFoundError`

- [ ] **Step 3: Write exceptions module**

Create `D:\Agent-Project\deep_research_scaffold\backend\app\core\exceptions.py`:
```python
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
```

- [ ] **Step 4: Run test to verify it passes**

```bash
cd /d/Agent-Project/deep_research_scaffold/backend
pytest tests/unit/test_exceptions.py -v
```

Expected: 5 tests pass

- [ ] **Step 5: Commit**

```bash
cd /d/Agent-Project/deep_research_scaffold
git add backend/app/core/exceptions.py backend/tests/unit/test_exceptions.py
git commit -m "feat(exceptions): add exception hierarchy"
```

---

## Phase 4: Security (JWT + Password)

### Task 6: Password hashing utility

**Files:**
- Create: `backend/app/core/security.py`
- Test: `backend/tests/unit/test_password.py`

- [ ] **Step 1: Write the failing test**

Create `D:\Agent-Project\deep_research_scaffold\backend\tests\unit\test_password.py`:
```python
from app.core.security import hash_password, verify_password


def test_hash_and_verify_password():
    plain = "my_secure_password_123"
    hashed = hash_password(plain)
    assert hashed != plain
    assert verify_password(plain, hashed) is True
    assert verify_password("wrong_password", hashed) is False


def test_hash_is_unique_per_call():
    plain = "same_password"
    h1 = hash_password(plain)
    h2 = hash_password(plain)
    assert h1 != h2  # bcrypt salt
    assert verify_password(plain, h1)
    assert verify_password(plain, h2)
```

- [ ] **Step 2: Run test to verify it fails**

```bash
cd /d/Agent-Project/deep_research_scaffold/backend
pytest tests/unit/test_password.py -v
```

Expected: FAIL with `ModuleNotFoundError`

- [ ] **Step 3: Write security module**

Create `D:\Agent-Project\deep_research_scaffold\backend\app\core\security.py`:
```python
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any
from uuid import UUID, uuid4

from jose import JWTError, jwt
from passlib.context import CryptContext

from app.core.config import get_settings

_pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def hash_password(plain: str) -> str:
    return _pwd_context.hash(plain)


def verify_password(plain: str, hashed: str) -> bool:
    try:
        return _pwd_context.verify(plain, hashed)
    except (ValueError, TypeError):
        return False


def create_access_token(
    *,
    user_id: int,
    tenant_id: UUID,
    roles: list[str],
    expires_in: int | None = None,
) -> tuple[str, str, int]:
    """Create access token. Returns (token, jti, expires_in_seconds)."""
    settings = get_settings()
    expires_in = expires_in or settings.jwt_access_ttl_seconds
    jti = str(uuid4())
    now = datetime.now(timezone.utc)
    payload: dict[str, Any] = {
        "sub": str(user_id),
        "tenant_id": str(tenant_id),
        "roles": roles,
        "iat": int(now.timestamp()),
        "exp": int((now + timedelta(seconds=expires_in)).timestamp()),
        "jti": jti,
        "type": "access",
    }
    token = jwt.encode(payload, settings.jwt_secret, algorithm=settings.jwt_algorithm)
    return token, jti, expires_in


def create_refresh_token(*, user_id: int, tenant_id: UUID) -> tuple[str, str]:
    settings = get_settings()
    now = datetime.now(timezone.utc)
    jti = str(uuid4())
    payload: dict[str, Any] = {
        "sub": str(user_id),
        "tenant_id": str(tenant_id),
        "iat": int(now.timestamp()),
        "exp": int((now + timedelta(seconds=settings.jwt_refresh_ttl_seconds)).timestamp()),
        "jti": jti,
        "type": "refresh",
    }
    token = jwt.encode(payload, settings.jwt_secret, algorithm=settings.jwt_algorithm)
    return token, jti


def decode_token(token: str) -> dict[str, Any]:
    settings = get_settings()
    try:
        payload = jwt.decode(token, settings.jwt_secret, algorithms=[settings.jwt_algorithm])
        return payload
    except JWTError as e:
        from app.core.exceptions import Unauthorized
        raise Unauthorized(f"Invalid token: {e}") from e
```

- [ ] **Step 4: Run test to verify it passes**

```bash
cd /d/Agent-Project/deep_research_scaffold/backend
pytest tests/unit/test_password.py -v
```

Expected: 2 tests pass

- [ ] **Step 5: Commit**

```bash
cd /d/Agent-Project/deep_research_scaffold
git add backend/app/core/security.py backend/tests/unit/test_password.py
git commit -m "feat(security): add password hashing utility"
```

---

### Task 7: JWT encode/decode tests

**Files:**
- Test: `backend/tests/unit/test_security.py`

- [ ] **Step 1: Write the failing test**

Create `D:\Agent-Project\deep_research_scaffold\backend\tests\unit\test_security.py`:
```python
import time
from uuid import uuid4

import pytest

from app.core.exceptions import Unauthorized
from app.core.security import (
    create_access_token,
    create_refresh_token,
    decode_token,
)


def test_access_token_round_trip():
    user_id = 42
    tenant_id = uuid4()
    token, jti, ttl = create_access_token(user_id=user_id, tenant_id=tenant_id, roles=["student"])
    assert ttl == 3600
    payload = decode_token(token)
    assert payload["sub"] == str(user_id)
    assert payload["tenant_id"] == str(tenant_id)
    assert payload["roles"] == ["student"]
    assert payload["jti"] == jti
    assert payload["type"] == "access"


def test_refresh_token_round_trip():
    user_id = 42
    tenant_id = uuid4()
    token, jti = create_refresh_token(user_id=user_id, tenant_id=tenant_id)
    payload = decode_token(token)
    assert payload["type"] == "refresh"
    assert payload["sub"] == str(user_id)


def test_decode_invalid_token_raises():
    with pytest.raises(Unauthorized):
        decode_token("not-a-real-jwt-token")


def test_decode_expired_token_raises(monkeypatch):
    from app.core import security

    # Patch settings to force 1-second TTL
    class FakeSettings:
        jwt_secret = "x" * 32
        jwt_algorithm = "HS256"
        jwt_access_ttl_seconds = 1

    monkeypatch.setattr(security, "get_settings", lambda: FakeSettings())
    token, _, _ = create_access_token(user_id=1, tenant_id=uuid4(), roles=[])
    time.sleep(2)
    with pytest.raises(Unauthorized):
        decode_token(token)
```

- [ ] **Step 2: Run test to verify it passes**

```bash
cd /d/Agent-Project/deep_research_scaffold/backend
pytest tests/unit/test_security.py -v
```

Expected: 4 tests pass

- [ ] **Step 3: Commit**

```bash
cd /d/Agent-Project/deep_research_scaffold
git add backend/tests/unit/test_security.py
git commit -m "test(security): add JWT round-trip and expiry tests"
```

---

## Phase 5: Database Models

### Task 8: SQLAlchemy Base and Mixins

**Files:**
- Create: `backend/app/models/base.py`

- [ ] **Step 1: Write base module**

Create `D:\Agent-Project\deep_research_scaffold\backend\app\models\base.py`:
```python
from __future__ import annotations

from datetime import datetime
from typing import Annotated
from uuid import UUID

from sqlalchemy import DateTime, ForeignKey, func
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    """SQLAlchemy declarative base."""


class TimestampMixin:
    """Adds created_at and updated_at columns."""

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )


class TenantScopedMixin(TimestampMixin):
    """Adds tenant_id FK and indexes every column with it."""

    tenant_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("tenants.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )


# Reusable annotated types
TenantId = Annotated[UUID, mapped_column(PGUUID(as_uuid=True), ForeignKey("tenants.id"))]
CreatedAt = Annotated[datetime, mapped_column(DateTime(timezone=True), server_default=func.now())]
UpdatedAt = Annotated[
    datetime,
    mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now()),
]
```

- [ ] **Step 2: Verify it imports**

```bash
cd /d/Agent-Project/deep_research_scaffold/backend
python -c "from app.models.base import Base, TenantScopedMixin, TimestampMixin; print('OK')"
```

Expected: `OK`

- [ ] **Step 3: Commit**

```bash
cd /d/Agent-Project/deep_research_scaffold
git add backend/app/models/base.py
git commit -m "feat(models): add SQLAlchemy Base + TenantScopedMixin"
```

---

### Task 9: Enum types

**Files:**
- Create: `backend/app/models/enums.py`

- [ ] **Step 1: Write enums module**

Create `D:\Agent-Project\deep_research_scaffold\backend\app\models\enums.py`:
```python
from __future__ import annotations

import enum


class UserRole(str, enum.Enum):
    student = "student"
    faculty = "faculty"
    librarian = "librarian"
    admin = "admin"


class UserStatus(str, enum.Enum):
    active = "active"
    suspended = "suspended"
    graduated = "graduated"


class BookStatus(str, enum.Enum):
    available = "available"
    borrowed = "borrowed"
    reserved = "reserved"
    lost = "lost"


class SeatStatus(str, enum.Enum):
    available = "available"
    occupied = "occupied"
    maintenance = "maintenance"
    disabled = "disabled"


class SeatZone(str, enum.Enum):
    silent = "silent"
    group = "group"
    individual = "individual"
    computer = "computer"


class AppointmentStatus(str, enum.Enum):
    pending = "pending"
    confirmed = "confirmed"
    active = "active"
    completed = "completed"
    cancelled = "cancelled"
    expired = "expired"


class AppointmentResource(str, enum.Enum):
    seat = "seat"
    book = "book"
    room = "room"


class TenantStatus(str, enum.Enum):
    active = "active"
    suspended = "suspended"
```

- [ ] **Step 2: Verify imports**

```bash
cd /d/Agent-Project/deep_research_scaffold/backend
python -c "from app.models.enums import UserRole, BookStatus, SeatStatus; print('OK')"
```

Expected: `OK`

- [ ] **Step 3: Commit**

```bash
cd /d/Agent-Project/deep_research_scaffold
git add backend/app/models/enums.py
git commit -m "feat(models): add enum types"
```

---

### Task 10: All domain models

**Files:**
- Create: `backend/app/models/tenant.py`
- Create: `backend/app/models/user.py`
- Create: `backend/app/models/book.py`
- Create: `backend/app/models/seat.py`
- Create: `backend/app/models/appointment.py`
- Create: `backend/app/models/policy.py`
- Create: `backend/app/models/__init__.py` (replace with imports)

- [ ] **Step 1: Write Tenant model**

Create `D:\Agent-Project\deep_research_scaffold\backend\app\models\tenant.py`:
```python
from __future__ import annotations

from uuid import UUID

from sqlalchemy import String
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin
from app.models.enums import TenantStatus


class Tenant(Base, TimestampMixin):
    __tablename__ = "tenants"

    id: Mapped[UUID] = mapped_column(primary_key=True)
    code: Mapped[str] = mapped_column(String(32), unique=True, nullable=False)
    name: Mapped[str] = mapped_column(String(128), nullable=False)
    status: Mapped[str] = mapped_column(String(16), nullable=False, default=TenantStatus.active.value)
    config: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
```

- [ ] **Step 2: Write User model**

Create `D:\Agent-Project\deep_research_scaffold\backend\app\models\user.py`:
```python
from __future__ import annotations

from datetime import datetime

from sqlalchemy import BigInteger, DateTime, ForeignKey, Index, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import TenantScopedMixin
from app.models.enums import UserRole, UserStatus


class User(TenantScopedMixin):
    __tablename__ = "users"
    __table_args__ = (
        UniqueConstraint("tenant_id", "student_no", name="uq_users_tenant_student_no"),
        Index("idx_users_tenant_role", "tenant_id", "role"),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    student_no: Mapped[str] = mapped_column(String(32), nullable=False)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    full_name: Mapped[str] = mapped_column(String(64), nullable=False)
    email: Mapped[str | None] = mapped_column(String(128))
    role: Mapped[str] = mapped_column(String(16), nullable=False, default=UserRole.student.value)
    status: Mapped[str] = mapped_column(String(16), nullable=False, default=UserStatus.active.value)
    last_login_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
```

- [ ] **Step 3: Write Book model**

Create `D:\Agent-Project\deep_research_scaffold\backend\app\models\book.py`:
```python
from __future__ import annotations

from datetime import datetime

from sqlalchemy import BigInteger, Index, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import TenantScopedMixin
from app.models.enums import BookStatus


class Book(TenantScopedMixin):
    __tablename__ = "books"
    __table_args__ = (
        Index("idx_books_tenant_title", "tenant_id", "title"),
        Index("idx_books_tenant_author", "tenant_id", "author"),
        Index("idx_books_tenant_category", "tenant_id", "category"),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    isbn: Mapped[str | None] = mapped_column(String(20))
    title: Mapped[str] = mapped_column(String(256), nullable=False)
    author: Mapped[str | None] = mapped_column(String(256))
    publisher: Mapped[str | None] = mapped_column(String(128))
    category: Mapped[str | None] = mapped_column(String(32))
    location: Mapped[str | None] = mapped_column(String(64))
    status: Mapped[str] = mapped_column(String(16), nullable=False, default=BookStatus.available.value)
    total_copies: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    available_copies: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    book_metadata: Mapped[dict] = mapped_column("metadata", JSONB, nullable=False, default=dict)
    indexed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
```

- [ ] **Step 4: Write Seat model**

Create `D:\Agent-Project\deep_research_scaffold\backend\app\models\seat.py`:
```python
from __future__ import annotations

from sqlalchemy import BigInteger, Boolean, Index, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import TenantScopedMixin
from app.models.enums import SeatStatus, SeatZone


class Seat(TenantScopedMixin):
    __tablename__ = "seats"
    __table_args__ = (
        UniqueConstraint("tenant_id", "code", name="uq_seats_tenant_code"),
        Index("idx_seats_tenant_floor", "tenant_id", "floor"),
        Index("idx_seats_tenant_status", "tenant_id", "status"),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    code: Mapped[str] = mapped_column(String(16), nullable=False)
    floor: Mapped[str] = mapped_column(String(8), nullable=False)
    zone: Mapped[str] = mapped_column(String(16), nullable=False, default=SeatZone.individual.value)
    status: Mapped[str] = mapped_column(String(16), nullable=False, default=SeatStatus.available.value)
    has_power: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    has_monitor: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    coord_x: Mapped[int] = mapped_column(Integer, nullable=False)
    coord_y: Mapped[int] = mapped_column(Integer, nullable=False)
```

- [ ] **Step 5: Write Appointment model**

Create `D:\Agent-Project\deep_research_scaffold\backend\app\models\appointment.py`:
```python
from __future__ import annotations

from datetime import datetime

from sqlalchemy import (
    BigInteger,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import TenantScopedMixin
from app.models.enums import AppointmentResource, AppointmentStatus


class Appointment(TenantScopedMixin):
    __tablename__ = "appointments"
    __table_args__ = (
        CheckConstraint("end_time > start_time", name="ck_appt_end_after_start"),
        Index(
            "idx_appt_resource_time",
            "tenant_id",
            "resource_type",
            "resource_id",
            "start_time",
            "end_time",
        ),
        Index("idx_appt_user_status", "tenant_id", "user_id", "status"),
        Index("idx_appt_status_endtime", "status", "end_time"),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("users.id"), nullable=False)
    resource_type: Mapped[str] = mapped_column(
        String(16), nullable=False, default=AppointmentResource.seat.value
    )
    resource_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    seat_id: Mapped[int | None] = mapped_column(BigInteger, ForeignKey("seats.id"))
    start_time: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    end_time: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    status: Mapped[str] = mapped_column(
        String(16), nullable=False, default=AppointmentStatus.pending.value
    )
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    confirmed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    cancelled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    cancel_reason: Mapped[str | None] = mapped_column(String(128))
```

- [ ] **Step 6: Write Policy model**

Create `D:\Agent-Project\deep_research_scaffold\backend\app\models\policy.py`:
```python
from __future__ import annotations

from datetime import datetime

from sqlalchemy import BigInteger, Date, Index, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import TenantScopedMixin


class Policy(TenantScopedMixin):
    __tablename__ = "policies"
    __table_args__ = (Index("idx_policies_tenant_category", "tenant_id", "category"),)

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    title: Mapped[str] = mapped_column(String(256), nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    category: Mapped[str | None] = mapped_column(String(32))
    effective_from: Mapped[datetime | None] = mapped_column(Date)
    effective_to: Mapped[datetime | None] = mapped_column(Date)
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    indexed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
```

- [ ] **Step 7: Write models __init__.py (replace with imports)**

Create `D:\Agent-Project\deep_research_scaffold\backend\app\models\__init__.py`:
```python
from app.models.appointment import Appointment
from app.models.base import Base, TenantScopedMixin, TimestampMixin
from app.models.book import Book
from app.models.enums import (
    AppointmentResource,
    AppointmentStatus,
    BookStatus,
    SeatStatus,
    SeatZone,
    TenantStatus,
    UserRole,
    UserStatus,
)
from app.models.policy import Policy
from app.models.seat import Seat
from app.models.tenant import Tenant
from app.models.user import User

__all__ = [
    "Appointment",
    "AppointmentResource",
    "AppointmentStatus",
    "Base",
    "Book",
    "BookStatus",
    "Policy",
    "Seat",
    "SeatStatus",
    "SeatZone",
    "Tenant",
    "TenantScopedMixin",
    "TenantStatus",
    "TimestampMixin",
    "User",
    "UserRole",
    "UserStatus",
]
```

- [ ] **Step 8: Verify all models import and create tables metadata**

```bash
cd /d/Agent-Project/deep_research_scaffold/backend
python -c "from app.models import Base, Tenant, User, Book, Seat, Appointment, Policy; print('Tables:', list(Base.metadata.tables.keys()))"
```

Expected: `Tables: ['tenants', 'users', 'books', 'seats', 'appointments', 'policies']`

- [ ] **Step 9: Commit**

```bash
cd /d/Agent-Project/deep_research_scaffold
git add backend/app/models
git commit -m "feat(models): add all domain models (tenant, user, book, seat, appointment, policy)"
```

---

### Task 11: Async database engine and session

**Files:**
- Create: `backend/app/core/database.py`

- [ ] **Step 1: Write database module**

Create `D:\Agent-Project\deep_research_scaffold\backend\app\core\database.py`:
```python
from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from app.core.config import get_settings

_engine: AsyncEngine | None = None
_session_factory: async_sessionmaker[AsyncSession] | None = None


def init_engine() -> AsyncEngine:
    """Initialize global engine (called from app lifespan)."""
    global _engine, _session_factory
    if _engine is not None:
        return _engine
    settings = get_settings()
    _engine = create_async_engine(
        settings.database_url,
        echo=settings.app_env == "development",
        pool_pre_ping=True,
        pool_size=10,
        max_overflow=20,
    )
    _session_factory = async_sessionmaker(_engine, expire_on_commit=False, class_=AsyncSession)
    return _engine


async def dispose_engine() -> None:
    global _engine, _session_factory
    if _engine is not None:
        await _engine.dispose()
    _engine = None
    _session_factory = None


def get_session_factory() -> async_sessionmaker[AsyncSession]:
    if _session_factory is None:
        init_engine()
    assert _session_factory is not None
    return _session_factory


@asynccontextmanager
async def get_db() -> AsyncIterator[AsyncSession]:
    """Context manager yielding a transactional session."""
    factory = get_session_factory()
    async with factory() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise


async def get_db_dependency() -> AsyncIterator[AsyncSession]:
    """FastAPI dependency yielding a session per request."""
    factory = get_session_factory()
    async with factory() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
```

- [ ] **Step 2: Verify imports**

```bash
cd /d/Agent-Project/deep_research_scaffold/backend
python -c "from app.core.database import init_engine, get_db, get_db_dependency; print('OK')"
```

Expected: `OK`

- [ ] **Step 3: Commit**

```bash
cd /d/Agent-Project/deep_research_scaffold
git add backend/app/core/database.py
git commit -m "feat(database): add async SQLAlchemy engine + session"
```

---

### Task 12: Alembic configuration

**Files:**
- Create: `backend/alembic.ini`
- Create: `backend/alembic/env.py`
- Create: `backend/alembic/script.py.mako`
- Create: `backend/alembic/versions/0001_initial.py`

- [ ] **Step 1: Initialize Alembic (programmatically)**

```bash
cd /d/Agent-Project/deep_research_scaffold/backend
mkdir -p alembic/versions
```

- [ ] **Step 2: Write alembic.ini**

Create `D:\Agent-Project\deep_research_scaffold\backend\alembic.ini`:
```ini
[alembic]
script_location = alembic
prepend_sys_path = .
sqlalchemy.url = postgresql://library:dev_password@localhost:5432/library
file_template = %%(year)d%%(month).2d%%(day).2d_%%(hour).2d%%(minute).2d_%%(rev)s_%%(slug)s

[loggers]
keys = root,sqlalchemy,alembic

[handlers]
keys = console

[formatters]
keys = generic

[logger_root]
level = WARNING
handlers = console
qualname =

[logger_sqlalchemy]
level = WARNING
handlers =
qualname = sqlalchemy.engine

[logger_alembic]
level = INFO
handlers =
qualname = alembic

[handler_console]
class = StreamHandler
args = (sys.stderr,)
level = NOTSET
formatter = generic

[formatter_generic]
format = %(levelname)-5.5s [%(name)s] %(message)s
datefmt = %H:%M:%S
```

- [ ] **Step 3: Write env.py**

Create `D:\Agent-Project\deep_research_scaffold\backend\alembic\env.py`:
```python
from __future__ import annotations

from logging.config import fileConfig

from alembic import context
from sqlalchemy import engine_from_config, pool

# Import settings + models to register metadata
from app.core.config import get_settings
from app.models import Base  # noqa: F401 - triggers model imports

config = context.config

# Override sqlalchemy.url from settings
settings = get_settings()
config.set_main_option("sqlalchemy.url", settings.database_url_sync)

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata


def run_migrations_offline() -> None:
    url = config.get_main_option("sqlalchemy.url")
    context.configure(url=url, target_metadata=target_metadata, literal_binds=True)
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )
    with connectable.connect() as connection:
        context.configure(connection=connection, target_metadata=target_metadata)
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
```

- [ ] **Step 4: Write script.py.mako**

Create `D:\Agent-Project\deep_research_scaffold\backend\alembic\script.py.mako`:
```mako
"""${message}

Revision ID: ${up_revision}
Revises: ${down_revision | comma,n}
Create Date: ${create_date}

"""
from __future__ import annotations

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
${imports if imports else ""}

# revision identifiers, used by Alembic.
revision: str = ${repr(up_revision)}
down_revision: Union[str, None] = ${repr(down_revision)}
branch_labels: Union[str, Sequence[str], None] = ${repr(branch_labels)}
depends_on: Union[str, Sequence[str], None] = ${repr(depends_on)}


def upgrade() -> None:
    ${upgrades if upgrades else "pass"}


def downgrade() -> None:
    ${downgrades if downgrades else "pass"}
```

- [ ] **Step 5: Generate initial migration**

```bash
cd /d/Agent-Project/deep_research_scaffold/backend
alembic revision --autogenerate -m "initial schema"
```

Expected: Creates `alembic/versions/0001_initial_schema.py` (or similar timestamp-based name)

- [ ] **Step 6: Verify migration file exists**

```bash
ls alembic/versions/
```

Expected: One .py file present

- [ ] **Step 7: Commit**

```bash
cd /d/Agent-Project/deep_research_scaffold
git add backend/alembic.ini backend/alembic
git commit -m "feat(db): add Alembic configuration and initial migration"
```

---

## Phase 6: Auth API

### Task 13: Auth schemas (Pydantic)

**Files:**
- Create: `backend/app/schemas/auth.py`
- Create: `backend/app/schemas/common.py`

- [ ] **Step 1: Write common schemas**

Create `D:\Agent-Project\deep_research_scaffold\backend\app\schemas\common.py`:
```python
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
```

- [ ] **Step 2: Write auth schemas**

Create `D:\Agent-Project\deep_research_scaffold\backend\app\schemas\auth.py`:
```python
from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, EmailStr, Field


class RegisterRequest(BaseModel):
    student_no: str = Field(..., min_length=4, max_length=32)
    password: str = Field(..., min_length=8, max_length=128)
    full_name: str = Field(..., min_length=1, max_length=64)
    email: EmailStr | None = None


class LoginRequest(BaseModel):
    student_no: str = Field(..., min_length=1)
    password: str = Field(..., min_length=1)


class RefreshRequest(BaseModel):
    refresh_token: str


class UserInfo(BaseModel):
    id: int
    student_no: str
    full_name: str
    email: str | None
    role: str
    tenant_id: str


class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: Literal["bearer"] = "bearer"
    expires_in: int
    user: UserInfo


class AccessTokenResponse(BaseModel):
    access_token: str
    token_type: Literal["bearer"] = "bearer"
    expires_in: int


class CurrentUserResponse(BaseModel):
    user: UserInfo
    tenant_id: str
    roles: list[str]
```

- [ ] **Step 3: Verify imports**

```bash
cd /d/Agent-Project/deep_research_scaffold/backend
python -c "from app.schemas.auth import LoginRequest, TokenResponse; from app.schemas.common import ErrorResponse; print('OK')"
```

Expected: `OK`

- [ ] **Step 4: Commit**

```bash
cd /d/Agent-Project/deep_research_scaffold
git add backend/app/schemas
git commit -m "feat(schemas): add auth and common Pydantic schemas"
```

---

### Task 14: User repository

**Files:**
- Create: `backend/app/repositories/user_repository.py`

- [ ] **Step 1: Write user repository**

Create `D:\Agent-Project\deep_research_scaffold\backend\app\repositories\user_repository.py`:
```python
from __future__ import annotations

from datetime import datetime, timezone
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import User


class UserRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def get_by_id(self, user_id: int, tenant_id: UUID) -> User | None:
        stmt = select(User).where(User.id == user_id, User.tenant_id == tenant_id)
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def get_by_student_no(self, student_no: str, tenant_id: UUID) -> User | None:
        stmt = select(User).where(User.student_no == student_no, User.tenant_id == tenant_id)
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def create(
        self,
        *,
        tenant_id: UUID,
        student_no: str,
        password_hash: str,
        full_name: str,
        email: str | None = None,
        role: str = "student",
    ) -> User:
        user = User(
            tenant_id=tenant_id,
            student_no=student_no,
            password_hash=password_hash,
            full_name=full_name,
            email=email,
            role=role,
        )
        self.session.add(user)
        await self.session.flush()
        await self.session.refresh(user)
        return user

    async def update_last_login(self, user_id: int) -> None:
        user = await self.session.get(User, user_id)
        if user is not None:
            user.last_login_at = datetime.now(timezone.utc)
            await self.session.flush()
```

- [ ] **Step 2: Verify imports**

```bash
cd /d/Agent-Project/deep_research_scaffold/backend
python -c "from app.repositories.user_repository import UserRepository; print('OK')"
```

Expected: `OK`

- [ ] **Step 3: Commit**

```bash
cd /d/Agent-Project/deep_research_scaffold
git add backend/app/repositories
git commit -m "feat(repositories): add user repository"
```

---

### Task 15: User service

**Files:**
- Create: `backend/app/services/user_service.py`

- [ ] **Step 1: Write user service**

Create `D:\Agent-Project\deep_research_scaffold\backend\app\services\user_service.py`:
```python
from __future__ import annotations

from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import Conflict, NotFound, Unauthorized
from app.core.security import hash_password, verify_password
from app.models import User
from app.repositories.user_repository import UserRepository


class UserService:
    def __init__(self, session: AsyncSession):
        self.session = session
        self.repo = UserRepository(session)

    async def register(
        self,
        *,
        tenant_id: UUID,
        student_no: str,
        password: str,
        full_name: str,
        email: str | None = None,
        role: str = "student",
    ) -> User:
        existing = await self.repo.get_by_student_no(student_no, tenant_id)
        if existing is not None:
            raise Conflict(f"Student number {student_no} already exists")
        return await self.repo.create(
            tenant_id=tenant_id,
            student_no=student_no,
            password_hash=hash_password(password),
            full_name=full_name,
            email=email,
            role=role,
        )

    async def authenticate(
        self, *, tenant_id: UUID, student_no: str, password: str
    ) -> User:
        user = await self.repo.get_by_student_no(student_no, tenant_id)
        if user is None:
            raise Unauthorized("Invalid credentials")
        if user.status != "active":
            raise Unauthorized("Account is not active")
        if not verify_password(password, user.password_hash):
            raise Unauthorized("Invalid credentials")
        await self.repo.update_last_login(user.id)
        return user

    async def get(self, user_id: int, tenant_id: UUID) -> User:
        user = await self.repo.get_by_id(user_id, tenant_id)
        if user is None:
            raise NotFound(f"User {user_id} not found")
        return user
```

- [ ] **Step 2: Verify imports**

```bash
cd /d/Agent-Project/deep_research_scaffold/backend
python -c "from app.services.user_service import UserService; print('OK')"
```

Expected: `OK`

- [ ] **Step 3: Commit**

```bash
cd /d/Agent-Project/deep_research_scaffold
git add backend/app/services
git commit -m "feat(services): add user service"
```

---

### Task 16: Auth dependency (current user)

**Files:**
- Create: `backend/app/api/deps.py`

- [ ] **Step 1: Write deps module**

Create `D:\Agent-Project\deep_research_scaffold\backend\app\api\deps.py`:
```python
from __future__ import annotations

from typing import Annotated
from uuid import UUID

from fastapi import Depends, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db_dependency
from app.core.exceptions import Unauthorized
from app.core.security import decode_token
from app.models import User
from app.services.user_service import UserService

_bearer_scheme = HTTPBearer(auto_error=False)


async def get_db(request: Request) -> AsyncSession:
    """FastAPI dependency wrapper around get_db_dependency."""
    async for session in get_db_dependency():
        yield session


async def get_current_user(
    request: Request,
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(_bearer_scheme)] = None,
    db: AsyncSession = Depends(get_db),
) -> User:
    """Extract JWT, decode, fetch user. Sets request.state.user_id and request.state.tenant_id."""
    if credentials is None or credentials.scheme.lower() != "bearer":
        raise Unauthorized("Missing bearer token")

    payload = decode_token(credentials.credentials)
    if payload.get("type") != "access":
        raise Unauthorized("Token is not an access token")

    user_id = int(payload["sub"])
    tenant_id = UUID(payload["tenant_id"])

    request.state.user_id = user_id
    request.state.tenant_id = tenant_id
    request.state.roles = set(payload.get("roles", []))

    service = UserService(db)
    return await service.get(user_id, tenant_id)
```

- [ ] **Step 2: Verify imports**

```bash
cd /d/Agent-Project/deep_research_scaffold/backend
python -c "from app.api.deps import get_db, get_current_user; print('OK')"
```

Expected: `OK`

- [ ] **Step 3: Commit**

```bash
cd /d/Agent-Project/deep_research_scaffold
git add backend/app/api/deps.py
git commit -m "feat(api): add FastAPI dependencies (db, current_user)"
```

---

### Task 17: Auth API endpoints

**Files:**
- Create: `backend/app/api/v1/auth.py`

- [ ] **Step 1: Write auth router**

Create `D:\Agent-Project\deep_research_scaffold\backend\app\api\v1\auth.py`:
```python
from __future__ import annotations

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, get_db
from app.core.config import get_settings
from app.core.exceptions import Unauthorized
from app.core.security import create_access_token, create_refresh_token, decode_token
from app.models import User
from app.schemas.auth import (
    AccessTokenResponse,
    CurrentUserResponse,
    LoginRequest,
    RefreshRequest,
    RegisterRequest,
    TokenResponse,
    UserInfo,
)
from app.services.user_service import UserService

router = APIRouter(prefix="/auth", tags=["auth"])


async def _resolve_default_tenant(db: AsyncSession) -> UUID:
    """MVP: single default tenant."""
    from sqlalchemy import select
    from app.models import Tenant

    settings = get_settings()
    stmt = select(Tenant).where(Tenant.code == settings.default_tenant_code)
    result = await db.execute(stmt)
    tenant = result.scalar_one_or_none()
    if tenant is None:
        raise RuntimeError(
            f"Default tenant '{settings.default_tenant_code}' not seeded. "
            "Run scripts/init_db.py first."
        )
    return tenant.id


@router.post("/register", response_model=TokenResponse, status_code=201)
async def register(
    payload: RegisterRequest,
    db: AsyncSession = Depends(get_db),
) -> TokenResponse:
    tenant_id = await _resolve_default_tenant(db)
    service = UserService(db)
    user = await service.register(
        tenant_id=tenant_id,
        student_no=payload.student_no,
        password=payload.password,
        full_name=payload.full_name,
        email=payload.email,
    )

    access_token, _, access_ttl = create_access_token(
        user_id=user.id, tenant_id=tenant_id, roles=[user.role]
    )
    refresh_token, _ = create_refresh_token(user_id=user.id, tenant_id=tenant_id)
    return TokenResponse(
        access_token=access_token,
        refresh_token=refresh_token,
        expires_in=access_ttl,
        user=UserInfo(
            id=user.id,
            student_no=user.student_no,
            full_name=user.full_name,
            email=user.email,
            role=user.role,
            tenant_id=str(tenant_id),
        ),
    )


@router.post("/login", response_model=TokenResponse)
async def login(
    payload: LoginRequest,
    db: AsyncSession = Depends(get_db),
) -> TokenResponse:
    tenant_id = await _resolve_default_tenant(db)
    service = UserService(db)
    user = await service.authenticate(
        tenant_id=tenant_id, student_no=payload.student_no, password=payload.password
    )
    access_token, _, access_ttl = create_access_token(
        user_id=user.id, tenant_id=tenant_id, roles=[user.role]
    )
    refresh_token, _ = create_refresh_token(user_id=user.id, tenant_id=tenant_id)
    return TokenResponse(
        access_token=access_token,
        refresh_token=refresh_token,
        expires_in=access_ttl,
        user=UserInfo(
            id=user.id,
            student_no=user.student_no,
            full_name=user.full_name,
            email=user.email,
            role=user.role,
            tenant_id=str(tenant_id),
        ),
    )


@router.post("/refresh", response_model=AccessTokenResponse)
async def refresh(
    payload: RefreshRequest,
    db: AsyncSession = Depends(get_db),
) -> AccessTokenResponse:
    token_payload = decode_token(payload.refresh_token)
    if token_payload.get("type") != "refresh":
        raise Unauthorized("Token is not a refresh token")

    user_id = int(token_payload["sub"])
    tenant_id = UUID(token_payload["tenant_id"])

    service = UserService(db)
    user = await service.get(user_id, tenant_id)

    access_token, _, access_ttl = create_access_token(
        user_id=user.id, tenant_id=tenant_id, roles=[user.role]
    )
    return AccessTokenResponse(access_token=access_token, expires_in=access_ttl)


@router.get("/me", response_model=CurrentUserResponse)
async def me(
    request: Request,
    user: User = Depends(get_current_user),
) -> CurrentUserResponse:
    return CurrentUserResponse(
        user=UserInfo(
            id=user.id,
            student_no=user.student_no,
            full_name=user.full_name,
            email=user.email,
            role=user.role,
            tenant_id=str(request.state.tenant_id),
        ),
        tenant_id=str(request.state.tenant_id),
        roles=list(request.state.roles),
    )
```

- [ ] **Step 2: Verify imports**

```bash
cd /d/Agent-Project/deep_research_scaffold/backend
python -c "from app.api.v1.auth import router; print('Routes:', [r.path for r in router.routes])"
```

Expected: `Routes: ['/register', '/login', '/refresh', '/me']` (or with /auth prefix)

- [ ] **Step 3: Commit**

```bash
cd /d/Agent-Project/deep_research_scaffold
git add backend/app/api/v1/auth.py
git commit -m "feat(api): add auth endpoints (register, login, refresh, me)"
```

---

### Task 18: Health endpoint

**Files:**
- Create: `backend/app/api/v1/health.py`

- [ ] **Step 1: Write health router**

Create `D:\Agent-Project\deep_research_scaffold\backend\app\api\v1\health.py`:
```python
from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_db

router = APIRouter(tags=["health"])


@router.get("/health")
async def health(db: AsyncSession = Depends(get_db)) -> dict:
    """Health check - verifies DB connectivity."""
    db_ok = True
    db_error: str | None = None
    try:
        await db.execute(text("SELECT 1"))
    except Exception as e:
        db_ok = False
        db_error = str(e)

    status = "ok" if db_ok else "degraded"
    return {
        "status": status,
        "components": {
            "database": {"ok": db_ok, "error": db_error},
        },
    }
```

- [ ] **Step 2: Verify imports**

```bash
cd /d/Agent-Project/deep_research_scaffold/backend
python -c "from app.api.v1.health import router; print('OK')"
```

Expected: `OK`

- [ ] **Step 3: Commit**

```bash
cd /d/Agent-Project/deep_research_scaffold
git add backend/app/api/v1/health.py
git commit -m "feat(api): add health check endpoint"
```

---

### Task 19: API v1 router aggregator

**Files:**
- Create: `backend/app/api/v1/router.py`

- [ ] **Step 1: Write router aggregator**

Create `D:\Agent-Project\deep_research_scaffold\backend\app\api\v1\router.py`:
```python
from __future__ import annotations

from fastapi import APIRouter

from app.api.v1.auth import router as auth_router
from app.api.v1.health import router as health_router

api_router = APIRouter(prefix="/api/v1")
api_router.include_router(auth_router)
api_router.include_router(health_router)
```

- [ ] **Step 2: Verify**

```bash
cd /d/Agent-Project/deep_research_scaffold/backend
python -c "from app.api.v1.router import api_router; print('Routes:', [(r.methods, r.path) for r in api_router.routes])"
```

Expected: All 5 routes listed (register, login, refresh, me, health)

- [ ] **Step 3: Commit**

```bash
cd /d/Agent-Project/deep_research_scaffold
git add backend/app/api/v1/router.py
git commit -m "feat(api): add v1 router aggregator"
```

---

### Task 20: Exception handlers and FastAPI app

**Files:**
- Create: `backend/app/main.py`
- Modify: `backend/app/core/observability.py` (create empty for now)

- [ ] **Step 1: Create observability stub (Plan 02 will fully implement)**

Create `D:\Agent-Project\deep_research_scaffold\backend\app\core\observability.py`:
```python
from __future__ import annotations

from app.core.config import get_settings


def init_observability() -> None:
    """Initialize OpenTelemetry tracing. Plan 04 will fully implement.

    For now this is a no-op so the app can start.
    """
    settings = get_settings()
    # TODO(plan-04): Set up OTel TracerProvider, MeterProvider, auto-instrumentation
    _ = settings  # silence unused


def shutdown_observability() -> None:
    """Shutdown OTel providers (Plan 04)."""
    pass
```

- [ ] **Step 2: Write main.py**

Create `D:\Agent-Project\deep_research_scaffold\backend\app\main.py`:
```python
from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from opentelemetry import trace

from app.api.v1.router import api_router
from app.core.config import get_settings
from app.core.database import dispose_engine, init_engine
from app.core.exceptions import LibraryBaseError
from app.core.observability import init_observability, shutdown_observability


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_observability()
    init_engine()
    yield
    await dispose_engine()
    shutdown_observability()


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(title=settings.app_name, version=settings.app_version, lifespan=lifespan)
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
```

- [ ] **Step 3: Verify app imports and starts**

```bash
cd /d/Agent-Project/deep_research_scaffold/backend
python -c "from app.main import app; print('Routes:', [(list(r.methods)[0] if r.methods else \"\", r.path) for r in app.routes])"
```

Expected: All 5 routes listed

- [ ] **Step 4: Commit**

```bash
cd /d/Agent-Project/deep_research_scaffold
git add backend/app/main.py backend/app/core/observability.py
git commit -m "feat(app): add FastAPI app with lifespan and exception handlers"
```

---

## Phase 7: Integration Tests

### Task 21: Test fixtures with testcontainers

**Files:**
- Create: `backend/tests/conftest.py`

- [ ] **Step 1: Write conftest.py**

Create `D:\Agent-Project\deep_research_scaffold\backend\tests\conftest.py`:
```python
from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator
from typing import Any

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from testcontainers.postgres import PostgresContainer

from app.core.config import Settings, get_settings
from app.core.database import get_db_dependency
from app.main import create_app
from app.models import Base


@pytest.fixture(scope="session")
def event_loop():
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()


@pytest.fixture(scope="session")
def postgres_container() -> Any:
    pg = PostgresContainer("postgres:15-alpine")
    pg.start()
    yield pg
    pg.stop()


@pytest.fixture(scope="session")
def test_settings(postgres_container: Any) -> Settings:
    """Settings override pointing to the test PostgreSQL container."""
    url = postgres_container.get_connection_url()
    # Convert postgresql:// to postgresql+asyncpg://
    async_url = url.replace("postgresql://", "postgresql+asyncpg://", 1)
    sync_url = url

    settings = Settings(
        postgres_password=postgres_container.POSTGRES_PASSWORD,
        jwt_secret="test_secret_minimum_32_characters_long_xx",
        app_env="test",
        log_level="WARNING",
    )
    # Override URLs manually
    object.__setattr__(settings, "database_url", async_url)
    object.__setattr__(settings, "database_url_sync", sync_url)
    return settings


@pytest_asyncio.fixture(scope="session")
async def engine(test_settings: Settings):
    eng = create_async_engine(test_settings.database_url)
    async with eng.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield eng
    await eng.dispose()


@pytest_asyncio.fixture
async def db_session(engine) -> AsyncIterator[AsyncSession]:
    factory = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)
    async with factory() as session:
        yield session
        await session.rollback()
        # Clean tables between tests
        async with engine.begin() as conn:
            for table in reversed(Base.metadata.sorted_tables):
                if table.name != "tenants":
                    await conn.execute(table.delete())


@pytest_asyncio.fixture
async def client(test_settings: Settings, engine) -> AsyncIterator[AsyncClient]:
    """HTTPX client with overridden DB session."""

    # Override get_settings
    get_settings.cache_clear()

    from app.core import config as config_module
    config_module.get_settings = lambda: test_settings

    # Override get_db_dependency
    factory = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)

    async def override_get_db():
        async with factory() as session:
            try:
                yield session
                await session.commit()
            except Exception:
                await session.rollback()
                raise

    app = create_app()
    app.dependency_overrides[get_db_dependency] = override_get_db

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        yield ac
```

- [ ] **Step 2: Verify conftest loads**

```bash
cd /d/Agent-Project/deep_research_scaffold/backend
pytest tests/conftest.py --collect-only -q 2>&1 | head -30
```

Expected: pytest collects without import errors

- [ ] **Step 3: Commit**

```bash
cd /d/Agent-Project/deep_research_scaffold
git add backend/tests/conftest.py
git commit -m "test: add testcontainers fixtures for PostgreSQL"
```

---

### Task 22: Health endpoint integration test

**Files:**
- Create: `backend/tests/integration/test_health.py`

- [ ] **Step 1: Write the failing test**

Create `D:\Agent-Project\deep_research_scaffold\backend\tests\integration\test_health.py`:
```python
import pytest

pytestmark = pytest.mark.integration


async def test_health_returns_ok(client):
    response = await client.get("/api/v1/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"
    assert data["components"]["database"]["ok"] is True


async def test_health_no_auth_required(client):
    """Health endpoint must work without Authorization header."""
    response = await client.get("/api/v1/health")  # no headers
    assert response.status_code == 200
```

- [ ] **Step 2: Run test**

```bash
cd /d/Agent-Project/deep_research_scaffold/backend
pytest tests/integration/test_health.py -v
```

Expected: 2 tests pass (requires Docker for testcontainers)

- [ ] **Step 3: Commit**

```bash
cd /d/Agent-Project/deep_research_scaffold
git add backend/tests/integration/test_health.py
git commit -m "test(integration): add health endpoint tests"
```

---

### Task 23: Auth API integration tests

**Files:**
- Create: `backend/tests/integration/test_auth_api.py`

- [ ] **Step 1: Write the test**

Create `D:\Agent-Project\deep_research_scaffold\backend\tests\integration\test_auth_api.py`:
```python
from uuid import UUID

import pytest

pytestmark = pytest.mark.integration


async def _seed_default_tenant(db_session):
    """Helper: ensure the default tenant exists for auth tests."""
    from app.models import Tenant

    existing = await db_session.get(Tenant, UUID("00000000-0000-0000-0000-000000000001"))
    if existing:
        return existing
    tenant = Tenant(
        id=UUID("00000000-0000-0000-0000-000000000001"),
        code="main_library",
        name="Main Library",
        status="active",
        config={},
    )
    db_session.add(tenant)
    await db_session.commit()
    return tenant


async def test_register_new_user_returns_tokens(client, db_session):
    await _seed_default_tenant(db_session)
    response = await client.post(
        "/api/v1/auth/register",
        json={
            "student_no": "2024001",
            "password": "strong_password_123",
            "full_name": "Test Student",
            "email": "test@example.com",
        },
    )
    assert response.status_code == 201, response.text
    data = response.json()
    assert data["token_type"] == "bearer"
    assert data["expires_in"] == 3600
    assert "access_token" in data
    assert "refresh_token" in data
    assert data["user"]["student_no"] == "2024001"
    assert data["user"]["role"] == "student"


async def test_register_duplicate_student_no_conflict(client, db_session):
    await _seed_default_tenant(db_session)
    payload = {
        "student_no": "2024002",
        "password": "strong_password_123",
        "full_name": "Test Student",
    }
    first = await client.post("/api/v1/auth/register", json=payload)
    assert first.status_code == 201

    second = await client.post("/api/v1/auth/register", json=payload)
    assert second.status_code == 409
    assert second.json()["error"]["code"] == "conflict"


async def test_register_validation_error_short_password(client, db_session):
    await _seed_default_tenant(db_session)
    response = await client.post(
        "/api/v1/auth/register",
        json={
            "student_no": "2024003",
            "password": "short",
            "full_name": "Test",
        },
    )
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "validation_error"


async def test_login_success(client, db_session):
    await _seed_default_tenant(db_session)
    await client.post(
        "/api/v1/auth/register",
        json={
            "student_no": "2024010",
            "password": "login_test_pwd",
            "full_name": "Login Test",
        },
    )

    response = await client.post(
        "/api/v1/auth/login",
        json={"student_no": "2024010", "password": "login_test_pwd"},
    )
    assert response.status_code == 200
    data = response.json()
    assert "access_token" in data


async def test_login_wrong_password_returns_401(client, db_session):
    await _seed_default_tenant(db_session)
    await client.post(
        "/api/v1/auth/register",
        json={
            "student_no": "2024011",
            "password": "correct_password",
            "full_name": "Wrong Pwd Test",
        },
    )

    response = await client.post(
        "/api/v1/auth/login",
        json={"student_no": "2024011", "password": "wrong_password"},
    )
    assert response.status_code == 401
    assert response.json()["error"]["code"] == "unauthorized"


async def test_me_returns_current_user(client, db_session):
    await _seed_default_tenant(db_session)
    reg = await client.post(
        "/api/v1/auth/register",
        json={
            "student_no": "2024020",
            "password": "me_test_pwd",
            "full_name": "Me Test",
        },
    )
    token = reg.json()["access_token"]

    response = await client.get(
        "/api/v1/auth/me", headers={"Authorization": f"Bearer {token}"}
    )
    assert response.status_code == 200
    data = response.json()
    assert data["user"]["student_no"] == "2024020"
    assert data["roles"] == ["student"]


async def test_me_without_token_returns_401(client):
    response = await client.get("/api/v1/auth/me")
    assert response.status_code == 401
    assert response.json()["error"]["code"] == "unauthorized"
```

- [ ] **Step 2: Run all tests**

```bash
cd /d/Agent-Project/deep_research_scaffold/backend
pytest tests/integration -v
```

Expected: All tests pass (health + auth)

- [ ] **Step 3: Commit**

```bash
cd /d/Agent-Project/deep_research_scaffold
git add backend/tests/integration/test_auth_api.py
git commit -m "test(integration): add auth API tests (register, login, refresh, me)"
```

---

## Phase 8: Database Initialization Script

### Task 24: Seed default tenant script

**Files:**
- Create: `backend/scripts/init_db.py`

- [ ] **Step 1: Write init_db.py**

Create `D:\Agent-Project\deep_research_scaffold\backend\scripts\init_db.py`:
```python
"""Initialize database: run migrations + seed default tenant."""
from __future__ import annotations

import asyncio
import sys
from pathlib import Path
from uuid import UUID

# Add backend to path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from alembic import command
from alembic.config import Config

from app.core.config import get_settings
from app.core.database import dispose_engine, init_engine
from app.models import Tenant
from sqlalchemy import select


def run_migrations() -> None:
    cfg = Config(str(Path(__file__).resolve().parent.parent / "alembic.ini"))
    cfg.set_main_option("sqlalchemy.url", get_settings().database_url_sync)
    command.upgrade(cfg, "head")


async def seed_default_tenant() -> None:
    settings = get_settings()
    init_engine()
    from app.core.database import get_session_factory

    factory = get_session_factory()
    async with factory() as session:
        stmt = select(Tenant).where(Tenant.code == settings.default_tenant_code)
        existing = (await session.execute(stmt)).scalar_one_or_none()
        if existing is not None:
            print(f"Tenant {settings.default_tenant_code} already exists (id={existing.id})")
            return

        tenant = Tenant(
            id=UUID("00000000-0000-0000-0000-000000000001"),
            code=settings.default_tenant_code,
            name="Main Library",
            status="active",
            config={},
        )
        session.add(tenant)
        await session.commit()
        print(f"Created default tenant: {tenant.id}")


async def main() -> None:
    print("Running migrations...")
    run_migrations()
    print("Seeding default tenant...")
    await seed_default_tenant()
    await dispose_engine()
    print("Done.")


if __name__ == "__main__":
    asyncio.run(main())
```

- [ ] **Step 2: Run the script (against Docker postgres in Task 25)**

We'll run this in Task 25 after Docker is set up.

- [ ] **Step 3: Commit**

```bash
cd /d/Agent-Project/deep_research_scaffold
git add backend/scripts
git commit -m "feat(scripts): add init_db.py for migrations and seed"
```

---

## Phase 9: Docker Compose

### Task 25: Dockerfile for backend

**Files:**
- Create: `backend/Dockerfile`

- [ ] **Step 1: Write Dockerfile**

Create `D:\Agent-Project\deep_research_scaffold\backend\Dockerfile`:
```dockerfile
FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /app

# Install system deps
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Install Python deps
COPY requirements.txt .
RUN pip install -r requirements.txt

# Copy app
COPY . .

EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
```

- [ ] **Step 2: Commit**

```bash
cd /d/Agent-Project/deep_research_scaffold
git add backend/Dockerfile
git commit -m "chore(docker): add backend Dockerfile"
```

---

### Task 26: docker-compose.yml

**Files:**
- Create: `deploy/docker-compose.yml`
- Create: `deploy/postgres/init.sql`

- [ ] **Step 1: Write postgres init.sql**

Create `D:\Agent-Project\deep_research_scaffold\deploy\postgres\init.sql`:
```sql
-- Enable extensions
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS "pg_trgm";
```

- [ ] **Step 2: Write docker-compose.yml**

Create `D:\Agent-Project\deep_research_scaffold\deploy\docker-compose.yml`:
```yaml
version: "3.9"

services:
  postgres:
    image: postgres:15-alpine
    environment:
      POSTGRES_DB: library
      POSTGRES_USER: library
      POSTGRES_PASSWORD: ${POSTGRES_PASSWORD:-dev_password}
    volumes:
      - postgres_data:/var/lib/postgresql/data
      - ./postgres/init.sql:/docker-entrypoint-initdb.d/init.sql:ro
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U library"]
      interval: 10s
      timeout: 5s
      retries: 5
    ports:
      - "5432:5432"

  api:
    build:
      context: ../backend
      dockerfile: Dockerfile
    command: ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
    environment:
      APP_ENV: development
      POSTGRES_HOST: postgres
      POSTGRES_PORT: 5432
      POSTGRES_USER: library
      POSTGRES_DB: library
      POSTGRES_PASSWORD: ${POSTGRES_PASSWORD:-dev_password}
      JWT_SECRET: ${JWT_SECRET:-dev_secret_minimum_32_characters_long_xx}
    depends_on:
      postgres:
        condition: service_healthy
    ports:
      - "8000:8000"

volumes:
  postgres_data:
```

- [ ] **Step 3: Write .env file for deploy**

Create `D:\Agent-Project\deep_research_scaffold\deploy\.env`:
```bash
POSTGRES_PASSWORD=dev_password
JWT_SECRET=dev_secret_minimum_32_characters_long_xx
```

- [ ] **Step 4: Build and start**

```bash
cd /d/Agent-Project/deep_research_scaffold/deploy
docker compose up -d --build
```

Expected: Both services start, postgres becomes healthy in ~10s.

- [ ] **Step 5: Run migrations + seed**

```bash
cd /d/Agent-Project/deep_research_scaffold
docker compose -f deploy/docker-compose.yml exec api python scripts/init_db.py
```

Expected:
```
Running migrations...
Seeding default tenant...
Created default tenant: 00000000-0000-0000-0000-000000000001
Done.
```

- [ ] **Step 6: Test health endpoint**

```bash
curl http://localhost:8000/api/v1/health
```

Expected: `{"status":"ok","components":{"database":{"ok":true,"error":null}}}`

- [ ] **Step 7: Test register endpoint**

```bash
curl -X POST http://localhost:8000/api/v1/auth/register \
  -H "Content-Type: application/json" \
  -d '{"student_no":"2024001","password":"test12345","full_name":"Test User"}'
```

Expected: 201 with token response

- [ ] **Step 8: Commit**

```bash
cd /d/Agent-Project/deep_research_scaffold
git add deploy
git commit -m "feat(deploy): add docker-compose with postgres + api"
```

---

### Task 27: docker-compose.dev.yml (hot reload)

**Files:**
- Create: `deploy/docker-compose.dev.yml`

- [ ] **Step 1: Write dev compose override**

Create `D:\Agent-Project\deep_research_scaffold\deploy\docker-compose.dev.yml`:
```yaml
services:
  api:
    build:
      target: null
    command: ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--reload"]
    volumes:
      - ../backend:/app
    environment:
      APP_ENV: development
```

- [ ] **Step 2: Test dev mode**

```bash
cd /d/Agent-Project/deep_research_scaffold/deploy
docker compose -f docker-compose.yml -f docker-compose.dev.yml up -d
```

Expected: API starts with hot reload enabled.

- [ ] **Step 3: Verify hot reload by editing a file**

Edit `backend/app/main.py` and add a print statement. Within a few seconds, the container should restart.

- [ ] **Step 4: Stop dev compose**

```bash
docker compose -f docker-compose.yml -f docker-compose.dev.yml down
```

- [ ] **Step 5: Commit**

```bash
cd /d/Agent-Project/deep_research_scaffold
git add deploy/docker-compose.dev.yml
git commit -m "feat(deploy): add docker-compose dev override with hot reload"
```

---

## Phase 10: CI Pipeline

### Task 28: GitHub Actions CI

**Files:**
- Create: `.github/workflows/ci.yml`

- [ ] **Step 1: Write CI workflow**

Create `D:\Agent-Project\deep_research_scaffold\.github\workflows\ci.yml`:
```yaml
name: CI

on:
  pull_request:
    branches: [main]
  push:
    branches: [main]

jobs:
  lint:
    runs-on: ubuntu-latest
    defaults:
      run:
        working-directory: backend
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: "3.12"
          cache: pip
          cache-dependency-path: backend/requirements.txt
      - name: Install
        working-directory: backend
        run: pip install -r requirements.txt
      - name: Ruff lint
        run: ruff check app/
      - name: Mypy
        run: mypy app/

  unit-test:
    runs-on: ubuntu-latest
    needs: lint
    defaults:
      run:
        working-directory: backend
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: "3.12"
          cache: pip
          cache-dependency-path: backend/requirements.txt
      - name: Install
        run: pip install -r requirements.txt
      - name: Unit tests
        run: pytest tests/unit -q --cov=app --cov-fail-under=75

  integration-test:
    runs-on: ubuntu-latest
    needs: lint
    services:
      postgres:
        image: postgres:15-alpine
        env:
          POSTGRES_USER: library
          POSTGRES_PASSWORD: test_password
          POSTGRES_DB: library
        ports:
          - 5432:5432
        options: >-
          --health-cmd pg_isready
          --health-interval 10s
          --health-timeout 5s
          --health-retries 5
    defaults:
      run:
        working-directory: backend
    env:
      POSTGRES_HOST: localhost
      POSTGRES_PASSWORD: test_password
      JWT_SECRET: test_secret_minimum_32_characters_long_xx
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: "3.12"
          cache: pip
          cache-dependency-path: backend/requirements.txt
      - name: Install
        run: pip install -r requirements.txt
      - name: Run migrations + seed
        run: python scripts/init_db.py
      - name: Integration tests
        run: pytest tests/integration -v --timeout=120
```

- [ ] **Step 2: Commit**

```bash
cd /d/Agent-Project/deep_research_scaffold
git add .github/workflows/ci.yml
git commit -m "ci: add GitHub Actions workflow (lint, unit, integration)"
```

---

## Phase 11: Documentation

### Task 29: Backend README

**Files:**
- Create: `backend/README.md`

- [ ] **Step 1: Write backend README**

Create `D:\Agent-Project\deep_research_scaffold\backend\README.md`:
```markdown
# Library Service Backend

FastAPI + SQLAlchemy + LangGraph backend for the Library Intelligent Service.

## Quick Start

### Local development

```bash
# Install dependencies
python -m venv .venv
source .venv/bin/activate  # or .venv\Scripts\activate on Windows
pip install -r requirements.txt

# Run with Docker (recommended)
cd ../deploy
docker compose -f docker-compose.yml -f docker-compose.dev.yml up
```

### Manual setup

```bash
# 1. Start PostgreSQL (any way)
# 2. Copy .env.example to .env and edit
cp .env.example .env

# 3. Run migrations + seed
python scripts/init_db.py

# 4. Start server
uvicorn app.main:app --reload --port 8000
```

## Testing

```bash
# Unit tests only (no Docker required)
pytest tests/unit -v

# Integration tests (requires Docker for testcontainers)
pytest tests/integration -v

# All tests with coverage
pytest --cov=app --cov-report=html
```

## API Endpoints

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| GET    | `/api/v1/health`        | No  | Health check |
| POST   | `/api/v1/auth/register` | No  | Register new user |
| POST   | `/api/v1/auth/login`    | No  | Login (returns tokens) |
| POST   | `/api/v1/auth/refresh`  | Yes | Refresh access token |
| GET    | `/api/v1/auth/me`       | Yes | Current user info |

## Project Layout

See `app/` directory for module breakdown.

## Configuration

All settings via environment variables. See `.env.example`.
```

- [ ] **Step 2: Commit**

```bash
cd /d/Agent-Project/deep_research_scaffold
git add backend/README.md
git commit -m "docs: add backend README"
```

---

### Task 30: Root README

**Files:**
- Create: `README.md`

- [ ] **Step 1: Write root README**

Create `D:\Agent-Project\deep_research_scaffold\README.md`:
```markdown
# Library Intelligent Service

基于 LangGraph 多 Agent + 自研四路召回 RAG 的高校图书馆智能服务系统。

## 状态

**当前里程碑**: Plan 01 — Infrastructure (in progress)

## 架构

- 后端: FastAPI + LangGraph v1 (位于 `backend/`)
- 数据库: PostgreSQL 15 + Redis 7
- 向量库: ChromaDB
- 部署: Docker Compose

详细设计见 `docs/superpowers/specs/2026-06-28-library-intelligent-service-design.md`

## 快速开始

```bash
# 1. 启动后端服务
cd deploy
docker compose up -d

# 2. 初始化数据库
docker compose exec api python scripts/init_db.py

# 3. 测试
curl http://localhost:8000/api/v1/health
```

## 路线图

- [x] Plan 01: 基础设施 + 鉴权 + DB schema
- [ ] Plan 02: 业务服务 + RAG 流水线
- [ ] Plan 03: LangGraph 多 Agent + Chat
- [ ] Plan 04: MCP Server + 可观测性
- [ ] Plan 05: 前端 + E2E 测试
```

- [ ] **Step 2: Commit**

```bash
cd /d/Agent-Project/deep_research_scaffold
git add README.md
git commit -m "docs: add root README with project status"
```

---

## Phase 12: Final Verification

### Task 31: Full system verification

- [ ] **Step 1: Stop any running services**

```bash
cd /d/Agent-Project/deep_research_scaffold/deploy
docker compose down -v
```

- [ ] **Step 2: Fresh start**

```bash
docker compose up -d --build
```

Expected: Both services start cleanly.

- [ ] **Step 3: Wait for health**

```bash
sleep 15
docker compose ps
```

Expected: Both `postgres` and `api` show "healthy" (or api "running").

- [ ] **Step 4: Run init script**

```bash
docker compose exec api python scripts/init_db.py
```

Expected: Tenant created successfully.

- [ ] **Step 5: Full e2e flow via curl**

```bash
# Health
curl -s http://localhost:8000/api/v1/health | jq

# Register
TOKEN_RESPONSE=$(curl -s -X POST http://localhost:8000/api/v1/auth/register \
  -H "Content-Type: application/json" \
  -d '{"student_no":"e2e_test","password":"e2e_test_pwd","full_name":"E2E Test"}')
echo $TOKEN_RESPONSE | jq
ACCESS_TOKEN=$(echo $TOKEN_RESPONSE | jq -r .access_token)

# Get current user
curl -s -H "Authorization: Bearer $ACCESS_TOKEN" http://localhost:8000/api/v1/auth/me | jq
```

Expected: All three commands return success JSON.

- [ ] **Step 6: Run full test suite**

```bash
cd /d/Agent-Project/deep_research_scaffold/backend
pytest tests/ -v --cov=app
```

Expected: All unit and integration tests pass; coverage > 75%.

- [ ] **Step 7: Verify lint passes**

```bash
cd /d/Agent-Project/deep_research_scaffold/backend
ruff check app/
mypy app/
```

Expected: No errors.

- [ ] **Step 8: Final commit if any fixes**

```bash
cd /d/Agent-Project/deep_research_scaffold
git status
# If anything changed:
git add -A
git commit -m "chore: post-verification fixes"
```

- [ ] **Step 9: Tag Plan 01 complete**

```bash
git tag -a plan-01-complete -m "Plan 01: Infrastructure complete"
git log --oneline | head -30
```

Expected: Clean linear history with ~30 commits, ending with Plan 01 tag.

---

## Acceptance Criteria

Plan 01 is complete when ALL of the following are true:

- [ ] `docker compose -f deploy/docker-compose.yml up -d` starts both services
- [ ] `docker compose exec api python scripts/init_db.py` creates the default tenant
- [ ] `curl http://localhost:8000/api/v1/health` returns `{"status":"ok",...}`
- [ ] `POST /api/v1/auth/register` creates a user and returns tokens
- [ ] `POST /api/v1/auth/login` authenticates and returns tokens
- [ ] `GET /api/v1/auth/me` returns current user when given valid bearer token
- [ ] `pytest tests/` passes 100% with coverage > 75%
- [ ] `ruff check app/` and `mypy app/` pass with zero errors
- [ ] GitHub Actions CI green on main branch
- [ ] All tables from spec §3 exist in PostgreSQL (verify with `\dt` in psql)

---

## Next Plan

After Plan 01 completes, proceed to **Plan 02 — Business Services + RAG Pipeline**:
- Book / Seat / Reservation REST endpoints
- RAG retriever implementations (BM25 + ChromaDB + RRF + Qwen3-rerank)
- Redis distributed lock utility
- Celery skeleton (no tasks yet)
