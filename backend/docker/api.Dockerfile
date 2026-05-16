# OJ API server image.
# Build from backend/ as context:
#   docker build -t codefyui-oj-api -f docker/api.Dockerfile .

FROM python:3.11-slim AS base

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    UV_LINK_MODE=copy

RUN apt-get update && apt-get install -y --no-install-recommends \
        curl ca-certificates \
    && rm -rf /var/lib/apt/lists/*

# Install uv
COPY --from=ghcr.io/astral-sh/uv:0.5.0 /uv /usr/local/bin/uv

WORKDIR /app

# Resolve and install dependencies (cached layer)
COPY pyproject.toml uv.lock README.md ./
RUN mkdir -p app && touch app/__init__.py && \
    uv sync --frozen --no-dev --no-install-project

# Copy application
COPY app/ ./app/
COPY alembic.ini ./
COPY alembic/ ./alembic/
COPY docker/entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh

# Install the project itself
RUN uv sync --frozen --no-dev

ENV PATH="/app/.venv/bin:$PATH"

# Pre-create storage subdirs so a mounted volume inherits oj ownership.
# Without this the volume is root-owned and the unprivileged process can't write.
RUN mkdir -p /app/storage/submissions /app/storage/problem_assets /app/storage/test_data

RUN useradd -m -u 10000 oj && chown -R oj:oj /app
USER oj

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=15s --retries=3 \
    CMD curl -fsS http://127.0.0.1:8000/api/health || exit 1

ENTRYPOINT ["/entrypoint.sh"]
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
