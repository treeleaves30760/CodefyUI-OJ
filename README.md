# CodefyUI-OJ

An Online Judge system designed to be used with [CodefyUI](https://github.com/treeleaves30760/CodefyUI). Students build computation graphs locally using cdui, export `graph.json`, and upload it to this system, where the server executes and grades the submission in a Docker sandbox.

## Features

- Account management (Student / Teacher / Admin roles)
- Problem management (statement, starter templates, hidden test cases, judge specification)
- Multiple concurrent contests (time windows, participants, scoring)
- Leaderboard
- Docker sandbox judging with hidden test case injection

## Quick Start (recommended: Docker Compose)

The fastest way to run the full stack — db, redis, api, worker, and the React frontend — is via the bundled `docker-compose.yml`.

Prerequisites: Docker ≥ 24 with the compose plugin.

```powershell
docker compose up -d --build
```

That brings up:

| Service | URL |
|---|---|
| Frontend (React + nginx) | http://localhost:8080 |
| API (FastAPI) | http://localhost:8100/api/health |
| Postgres | localhost:5432 (user `oj`, pw `oj-dev`, db `codefyui_oj`) |
| Redis | localhost:6379 |

The API runs `alembic upgrade head` on every boot, so the schema is ready immediately. Open http://localhost:8080 and register an account to verify everything is wired up.

Useful commands:

```powershell
# Tail logs
docker compose logs -f api

# Stop everything (keep volumes)
docker compose down

# Stop and wipe the database
docker compose down -v

# Rebuild after code changes
docker compose up -d --build
```

> **Note on judging:** the bundled dev stack runs the judge in subprocess mode and does not include the cdui repo, so submissions will fail to be scored until you either bind-mount cdui into the worker or switch to the production stack with the sandbox image. Account creation, login, and problem/contest management work fully.

## Architecture

See the [implementation plan](../.claude/plans/oj-cdui-json-oj-codefyui-oj-crystalline-plum.md) for details.

```
┌──────────┐  graph.json   ┌─────────────┐         ┌──────────┐
│ Student  │ ─────────────▶│ OJ API      │ enqueue │ Judge    │
│ cdui     │               │ (FastAPI)   │ ───────▶│ Worker   │
└──────────┘               └─────────────┘         │ (Docker  │
                                                   │ sandbox) │
                                                   └──────────┘
```

## Development without Docker

Prefer the Docker workflow above. The manual workflow is here for backend/frontend hacking with hot reload.

Prerequisites:

- [uv](https://docs.astral.sh/uv/) ≥ 0.5
- Node.js ≥ 20, pnpm or npm
- Docker (for db/redis, and for the sandbox image from Phase 4 on)

### Postgres + Redis only

```powershell
docker compose up -d db redis
```

### Backend

```powershell
cd backend
uv sync --extra dev
uv run uvicorn app.main:app --reload --port 8100
# GET http://localhost:8100/api/health
```

### Frontend

```powershell
cd frontend
pnpm install
pnpm dev
# http://localhost:5173  (Vite proxies /api → http://localhost:8100)
```

## Deployment

Full production deployment guide: [docs/deployment.md](docs/deployment.md).

Quick overview:
1. Clone both the CodefyUI and CodefyUI-OJ repositories
2. `cp .env.prod.example .env.prod` and edit passwords / JWT secret / CORS
3. Run `./backend/docker/build_sandbox.sh` (or `.ps1`) to build the sandbox image
4. `docker compose --env-file .env.prod -f docker-compose.prod.yml up -d --build`
5. Set up nginx as a reverse proxy with HTTPS

## Project Status

| Phase | Content | Status |
|---|---|---|
| 0 | Repo + scaffold + smoke | ✅ |
| 1 | Auth (fastapi-users + JWT) | ✅ |
| 2 | Problems CRUD + JudgeSpec | ✅ |
| 3 | Submissions + sandbox judging pipeline (dev mode) | ✅ |
| 4 | Docker sandbox image | ✅ |
| 5 | Contests + leaderboard | ✅ |
| 6 | Production Docker compose | ✅ |
| — | Email verification / SSO | Not implemented |
| — | Realtime leaderboard SSE | Not implemented |
| — | Rate limit middleware | Not implemented |

## License

AGPL-3.0 (consistent with CodefyUI). See `LICENSE` for details.
