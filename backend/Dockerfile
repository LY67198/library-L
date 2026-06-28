FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_NO_CACHE=1

WORKDIR /app

# Install system deps (uv needs curl for binary install fallback)
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Install uv
RUN pip install uv

# Install Python deps via uv (using requirements.txt for Docker simplicity)
COPY requirements.txt .
RUN uv pip install --system -r requirements.txt

# Install alembic + psycopg2-binary for migrations
RUN uv pip install --system alembic psycopg2-binary

# Copy app
COPY . .

EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
