#!/usr/bin/env bash
# Entrypoint for OJ API container.
# Runs alembic migrations against the configured database, then exec'd into
# the CMD (uvicorn). Migrations are idempotent — safe to run on every boot.

set -euo pipefail

if [[ "${SKIP_MIGRATIONS:-false}" != "true" ]]; then
    echo "[entrypoint] running alembic upgrade head"
    alembic upgrade head
fi

exec "$@"
