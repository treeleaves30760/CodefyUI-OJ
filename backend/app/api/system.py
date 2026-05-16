from fastapi import APIRouter, Depends, HTTPException, status
from fastapi_users.exceptions import UserAlreadyExists
from pydantic import BaseModel, EmailStr, Field
from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.core.security import UserManager, get_user_manager
from app.db import get_async_session
from app.models.problem import Problem
from app.models.user import User, UserRole
from app.schemas.user import UserCreate, UserRead

router = APIRouter()


class SystemStatus(BaseModel):
    mode: str
    initialized: bool
    practice_problem_count: int


class AdminSetupPayload(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)
    display_name: str = Field(min_length=1, max_length=80)


async def _count_admins(session: AsyncSession) -> int:
    stmt = select(func.count(User.id)).where(
        or_(User.role == UserRole.admin, User.is_superuser.is_(True)),
    )
    return (await session.scalar(stmt)) or 0


async def _count_practice_problems(session: AsyncSession) -> int:
    stmt = select(func.count(Problem.id)).where(
        Problem.published.is_(True),
        Problem.practice_visible.is_(True),
    )
    return (await session.scalar(stmt)) or 0


@router.get("/status", response_model=SystemStatus)
async def get_status(
    session: AsyncSession = Depends(get_async_session),
) -> SystemStatus:
    settings = get_settings()
    if settings.app_mode == "practice":
        return SystemStatus(
            mode="practice",
            initialized=True,
            practice_problem_count=await _count_practice_problems(session),
        )

    admin_count = await _count_admins(session)
    return SystemStatus(
        mode="competition",
        initialized=admin_count > 0,
        practice_problem_count=0,
    )


@router.post(
    "/setup",
    response_model=UserRead,
    status_code=status.HTTP_201_CREATED,
)
async def setup_first_admin(
    payload: AdminSetupPayload,
    session: AsyncSession = Depends(get_async_session),
    user_manager: UserManager = Depends(get_user_manager),
) -> User:
    settings = get_settings()
    if settings.app_mode != "competition":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="setup is only available in competition mode",
        )

    if await _count_admins(session) > 0:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="system already initialized",
        )

    user_create = UserCreate(
        email=payload.email,
        password=payload.password,
        display_name=payload.display_name,
        is_active=True,
        is_superuser=True,
        is_verified=True,
    )
    try:
        user = await user_manager.create(user_create, safe=False)
    except UserAlreadyExists as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="email already registered",
        ) from exc

    user.role = UserRole.admin
    session.add(user)
    await session.commit()
    await session.refresh(user)
    return user
