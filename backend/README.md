# CodefyUI-OJ Backend

FastAPI + SQLAlchemy + Alembic + fastapi-users + RQ.

## Quickstart

```powershell
# 安裝
uv sync --extra dev

# 複製環境變數
Copy-Item .env.example .env

# 啟動 API
uv run uvicorn app.main:app --reload --port 8100

# 試打 health
curl http://localhost:8100/api/health
```

## 結構

```
app/
├── main.py              # FastAPI app factory
├── config.py            # Settings via pydantic-settings
├── db.py                # SQLAlchemy async engine + session  [Phase 1]
├── deps.py              # FastAPI dependencies               [Phase 1]
├── models/              # SQLAlchemy models                  [Phase 1+]
├── schemas/             # Pydantic schemas                   [Phase 1+]
├── api/                 # Route modules                      [Phase 1+]
├── core/                # security, storage, queue           [Phase 1+]
└── judge/               # worker + runner + patcher          [Phase 3+]

tests/                   # pytest
alembic/                 # migrations                          [Phase 1]
docker/                  # Dockerfiles                         [Phase 4]
```

## 測試

```powershell
uv run pytest
```
