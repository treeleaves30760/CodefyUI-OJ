# OJ RQ worker image. Spawns sandbox containers per submission.
# Build from backend/ as context:
#   docker build -t codefyui-oj-worker -f docker/worker.Dockerfile .

FROM python:3.11-slim AS base

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    UV_LINK_MODE=copy

RUN apt-get update && apt-get install -y --no-install-recommends \
        curl ca-certificates docker.io \
    && rm -rf /var/lib/apt/lists/*

COPY --from=ghcr.io/astral-sh/uv:0.5.0 /uv /usr/local/bin/uv

WORKDIR /app

COPY pyproject.toml uv.lock README.md ./
RUN mkdir -p app && touch app/__init__.py && \
    uv sync --frozen --no-dev --no-install-project

COPY app/ ./app/
COPY sandbox/ ./sandbox/
RUN uv sync --frozen --no-dev

ENV PATH="/app/.venv/bin:$PATH"

ENTRYPOINT ["python", "-m", "app.judge.worker"]
