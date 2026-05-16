# CodefyUI-OJ

An Online Judge system designed to be used with [CodefyUI](https://github.com/treeleaves30760/CodefyUI). Students build computation graphs locally using cdui, export `graph.json`, and upload it to this system, where the server executes and grades the submission in a Docker sandbox.

## Features

- Account management (Student / Teacher / Admin roles)
- Problem management (statement, starter templates, hidden test cases, judge specification)
- Multiple concurrent contests (time windows, participants, scoring)
- Leaderboard
- Docker sandbox judging with hidden test case injection

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

## Development

Prerequisites:

- [uv](https://docs.astral.sh/uv/) ≥ 0.5
- Node.js ≥ 20, pnpm or npm
- Docker ≥ 24 (required starting from Phase 4 for the sandbox container)

### Backend

```powershell
cd backend
uv sync --extra dev
uv run uvicorn app.main:app --reload --port 8000
# GET http://localhost:8000/api/health
```

### Frontend

```powershell
cd frontend
pnpm install
pnpm dev
# http://localhost:5173
```

### Postgres + Redis (dev)

```powershell
docker compose up -d db redis
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
