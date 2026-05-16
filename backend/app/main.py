import logging
import os
import secrets
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi_users.db import SQLAlchemyUserDatabase
from fastapi_users.exceptions import UserAlreadyExists
from fastapi_users.password import PasswordHelper
from sqlalchemy import func, or_, select

from app.api import auth as auth_api
from app.api import contests as contests_api
from app.api import leaderboard as leaderboard_api
from app.api import problems as problems_api
from app.api import submissions as submissions_api
from app.api import system as system_api
from app.api import users as users_api
from app.config import (
    PRACTICE_USER_DISPLAY_NAME,
    PRACTICE_USER_EMAIL,
    get_settings,
)
from app.core.security import UserManager
from app.db import async_session_maker
from app.models.user import User, UserRole
from app.schemas.user import UserCreate

log = logging.getLogger(__name__)


async def _ensure_practice_user() -> None:
    async with async_session_maker() as session:
        existing = await session.execute(
            select(User).where(User.email == PRACTICE_USER_EMAIL)
        )
        if existing.scalar_one_or_none() is not None:
            return
        # Bypass UserManager/EmailStr validation because PRACTICE_USER_EMAIL may
        # use a reserved TLD like .local that pydantic rejects, and nobody ever
        # logs in as this user anyway — it just owns submissions.
        helper = PasswordHelper()
        user = User(
            email=PRACTICE_USER_EMAIL,
            hashed_password=helper.hash(secrets.token_urlsafe(32)),
            display_name=PRACTICE_USER_DISPLAY_NAME,
            role=UserRole.student,
            is_active=True,
            is_superuser=False,
            is_verified=True,
        )
        session.add(user)
        try:
            await session.commit()
            log.info("practice user provisioned: %s", PRACTICE_USER_EMAIL)
        except Exception:
            await session.rollback()
            # Race-safe: another worker provisioned it concurrently.
            existing2 = await session.execute(
                select(User).where(User.email == PRACTICE_USER_EMAIL)
            )
            if existing2.scalar_one_or_none() is None:
                raise


async def _bootstrap_admin_from_env() -> None:
    settings = get_settings()
    if not (settings.bootstrap_admin_email and settings.bootstrap_admin_password):
        return

    async with async_session_maker() as session:
        admin_count = (
            await session.scalar(
                select(func.count(User.id)).where(
                    or_(User.role == UserRole.admin, User.is_superuser.is_(True)),
                ),
            )
            or 0
        )
        if admin_count > 0:
            return

        manager = UserManager(SQLAlchemyUserDatabase(session, User))
        try:
            user = await manager.create(
                UserCreate(
                    email=settings.bootstrap_admin_email,
                    password=settings.bootstrap_admin_password,
                    display_name=settings.bootstrap_admin_display_name,
                    is_active=True,
                    is_superuser=True,
                    is_verified=True,
                ),
                safe=False,
            )
            user.role = UserRole.admin
            session.add(user)
            await session.commit()
            log.info("admin bootstrapped from env: %s", settings.bootstrap_admin_email)
        except UserAlreadyExists:
            # Email already exists but wasn't admin -> promote it.
            existing = await session.scalar(
                select(User).where(User.email == settings.bootstrap_admin_email),
            )
            if existing and not existing.is_superuser:
                existing.is_superuser = True
                existing.role = UserRole.admin
                await session.commit()
                log.info(
                    "existing user promoted to admin via env: %s",
                    settings.bootstrap_admin_email,
                )


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = get_settings()
    settings.storage_root.mkdir(parents=True, exist_ok=True)
    settings.submissions_dir.mkdir(parents=True, exist_ok=True)
    settings.problem_assets_dir.mkdir(parents=True, exist_ok=True)
    settings.test_data_dir.mkdir(parents=True, exist_ok=True)

    if settings.app_mode == "practice":
        await _ensure_practice_user()
    else:
        await _bootstrap_admin_from_env()

    # Seed baseline problems if an owner is available. Idempotent and
    # skips cleanly when no admin exists yet (competition mode before setup).
    if os.environ.get("OJ_SEED_ENABLED", "true").lower() in ("1", "true", "yes", "on"):
        try:
            from app.seeding.runner import seed as run_seed

            await run_seed()
        except Exception:  # noqa: BLE001
            log.exception("seed failed in lifespan; continuing without baseline data")

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
        system_api.router,
        prefix=f"{settings.api_prefix}/system",
        tags=["system"],
    )

    # Auth + user management are competition-mode only. Practice mode has no
    # login concept; everything resolves to the shared practice user.
    if settings.app_mode == "competition":
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

    # Contests don't exist in practice mode (no admin to create them, no
    # multi-user notion). Skip routing entirely so the API surface is honest.
    if settings.app_mode == "competition":
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
