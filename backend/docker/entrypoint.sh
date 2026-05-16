#!/usr/bin/env bash
# Entrypoint for OJ API container.
# Runs alembic migrations against the configured database, then exec's into
# the CMD (uvicorn). The application's lifespan handles:
#   - admin bootstrap from BOOTSTRAP_ADMIN_* env (competition mode), or
#   - practice user provisioning (APP_MODE=practice), then
#   - baseline problem seeding (if OJ_SEED_ENABLED=true and an owner exists).
# All idempotent — safe to run on every boot.

set -euo pipefail

if [[ "${SKIP_MIGRATIONS:-false}" != "true" ]]; then
    echo "[entrypoint] running alembic upgrade head"
    alembic upgrade head
fi

exec "$@"
