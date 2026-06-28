# Library Service Backend

FastAPI + SQLAlchemy + LangGraph backend for the Library Intelligent Service.

## Quick Start

### Local development (uv — required)

```bash
# Install dependencies (creates .venv + uv.lock)
uv sync --extra dev

# Run with Docker (recommended — handles Postgres too)
cd ../deploy
docker compose -f docker-compose.yml -f docker-compose.dev.yml up
```

### Manual setup

```bash
# 1. Start PostgreSQL (any way: Docker, local install, etc.)
# 2. Copy .env.example to .env and edit
cp .env.example .env

# 3. Run migrations + seed
uv run python scripts/init_db.py

# 4. Start server
uv run uvicorn app.main:app --reload --port 8000
```

## Testing

```bash
# Unit tests only (no Docker required)
uv run pytest tests/unit -v

# Integration tests (requires Docker daemon for testcontainers)
uv run pytest tests/integration -v

# All tests with coverage
uv run pytest --cov=app --cov-report=html
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

```
backend/
├── app/
│   ├── main.py            # FastAPI app + lifespan
│   ├── core/              # config, database, security, exceptions, observability
│   ├── api/v1/            # routes: auth, health
│   ├── schemas/           # Pydantic request/response models
│   ├── models/            # SQLAlchemy ORM (all with tenant_id)
│   ├── repositories/      # Data access layer
│   └── services/          # Business logic
├── alembic/               # DB migrations
├── scripts/init_db.py     # Migrate + seed
├── tests/unit/            # Pure-function tests
├── tests/integration/     # testcontainers-based DB tests
├── pyproject.toml         # UV-managed dependencies
└── Dockerfile
```

## Configuration

All settings via environment variables. See `.env.example`.
