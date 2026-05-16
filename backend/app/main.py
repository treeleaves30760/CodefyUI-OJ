from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api import auth as auth_api
from app.api import contests as contests_api
from app.api import leaderboard as leaderboard_api
from app.api import problems as problems_api
from app.api import submissions as submissions_api
from app.api import users as users_api
from app.config import get_settings


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = get_settings()
    settings.storage_root.mkdir(parents=True, exist_ok=True)
    settings.submissions_dir.mkdir(parents=True, exist_ok=True)
    settings.problem_assets_dir.mkdir(parents=True, exist_ok=True)
    settings.test_data_dir.mkdir(parents=True, exist_ok=True)
    yield


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(
        title=settings.app_name,
        debug=settings.debug,
        lifespan=lifespan,
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.get(f"{settings.api_prefix}/health", tags=["meta"])
    async def health() -> dict[str, str]:
        return {"status": "ok", "app": settings.app_name}

    app.include_router(
        auth_api.router,
        prefix=f"{settings.api_prefix}/auth",
    )
    app.include_router(
        users_api.router,
        prefix=f"{settings.api_prefix}/users",
        tags=["users"],
    )
    app.include_router(
        problems_api.router,
        prefix=f"{settings.api_prefix}/problems",
        tags=["problems"],
    )
    app.include_router(
        submissions_api.router,
        prefix=f"{settings.api_prefix}/submissions",
        tags=["submissions"],
    )
    app.include_router(
        contests_api.router,
        prefix=f"{settings.api_prefix}/contests",
        tags=["contests"],
    )
    app.include_router(
        leaderboard_api.router,
        prefix=f"{settings.api_prefix}/contests",
        tags=["leaderboard"],
    )

    return app


app = create_app()
