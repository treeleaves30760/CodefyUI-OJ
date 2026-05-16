from collections.abc import AsyncGenerator

from fastapi import Depends, HTTPException, status
from fastapi_users import BaseUserManager, FastAPIUsers, IntegerIDMixin
from fastapi_users.authentication import (
    AuthenticationBackend,
    BearerTransport,
    JWTStrategy,
)
from fastapi_users.db import SQLAlchemyUserDatabase
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import PRACTICE_USER_EMAIL, get_settings
from app.db import get_async_session
from app.models.user import User


class UserManager(IntegerIDMixin, BaseUserManager[User, int]):
    @property
    def reset_password_token_secret(self) -> str:
        return get_settings().jwt_secret

    @property
    def verification_token_secret(self) -> str:
        return get_settings().jwt_secret


async def get_user_db(
    session: AsyncSession = Depends(get_async_session),
) -> AsyncGenerator[SQLAlchemyUserDatabase, None]:
    yield SQLAlchemyUserDatabase(session, User)


async def get_user_manager(
    user_db: SQLAlchemyUserDatabase = Depends(get_user_db),
) -> AsyncGenerator[UserManager, None]:
    yield UserManager(user_db)


bearer_transport = BearerTransport(tokenUrl="api/auth/jwt/login")


def get_jwt_strategy() -> JWTStrategy:
    settings = get_settings()
    return JWTStrategy(
        secret=settings.jwt_secret,
        lifetime_seconds=settings.jwt_lifetime_seconds,
    )


auth_backend = AuthenticationBackend(
    name="jwt",
    transport=bearer_transport,
    get_strategy=get_jwt_strategy,
)


fastapi_users = FastAPIUsers[User, int](get_user_manager, [auth_backend])


async def _practice_user_dependency(
    session: AsyncSession = Depends(get_async_session),
) -> User:
    """Resolve every request as the shared practice user (no auth)."""
    result = await session.execute(
        select(User).where(User.email == PRACTICE_USER_EMAIL)
    )
    user = result.scalar_one_or_none()
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="practice user not provisioned",
        )
    return user


def _resolve_current_active_user():
    if get_settings().app_mode == "practice":
        return _practice_user_dependency
    return fastapi_users.current_user(active=True)


def _resolve_optional_active_user():
    """Like ``current_active_user`` but returns ``None`` when unauthenticated.

    Used by endpoints that should be browsable without login (e.g. the public
    problem catalog). Practice mode still resolves to the shared practice user
    so downstream filtering stays uniform.
    """
    if get_settings().app_mode == "practice":
        return _practice_user_dependency
    return fastapi_users.current_user(active=True, optional=True)


def _resolve_current_superuser():
    if get_settings().app_mode == "practice":
        async def _denied() -> User:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="superuser endpoints disabled in practice mode",
            )

        return _denied
    return fastapi_users.current_user(active=True, superuser=True)


current_active_user = _resolve_current_active_user()
optional_active_user = _resolve_optional_active_user()
current_superuser = _resolve_current_superuser()
