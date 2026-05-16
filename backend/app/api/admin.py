"""Admin-only console API.

All endpoints require role=admin (or is_superuser). Reuses the existing
require_admin permission dependency. Provides system stats, user
management with self-protection and last-admin guard, and a global
submissions feed.
"""
from datetime import datetime, timedelta, timezone
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, ConfigDict
from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.permissions import require_admin
from app.db import get_async_session
from app.models.contest import Contest
from app.models.problem import Problem
from app.models.submission import Submission, SubmissionStatus
from app.models.user import User, UserRole

router = APIRouter()


# ---------------------------------------------------------------------------
# Schemas
# ---------------------------------------------------------------------------


class AdminStats(BaseModel):
    users_total: int
    users_by_role: dict[str, int]
    problems_total: int
    problems_published: int
    contests_total: int
    contests_active: int
    submissions_total: int
    submissions_last_24h: int


class AdminUserRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    email: str
    display_name: str
    role: UserRole
    is_active: bool
    is_superuser: bool
    created_at: datetime


class AdminUserUpdate(BaseModel):
    role: UserRole | None = None
    is_active: bool | None = None


class AdminSubmissionRow(BaseModel):
    id: int
    user_id: int
    user_email: str
    problem_id: int
    problem_slug: str
    contest_id: int | None
    status: SubmissionStatus
    score: float | None
    submitted_at: datetime


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


async def _count_admins(session: AsyncSession) -> int:
    stmt = select(func.count(User.id)).where(
        User.is_active.is_(True),
        or_(User.role == UserRole.admin, User.is_superuser.is_(True)),
    )
    return int((await session.scalar(stmt)) or 0)


def _would_remain_admin(user: User, *, new_role: UserRole | None, new_active: bool | None) -> bool:
    """Return True if `user` would still be a usable admin after the patch."""
    role = new_role if new_role is not None else user.role
    active = new_active if new_active is not None else user.is_active
    is_admin = role == UserRole.admin or user.is_superuser
    return bool(active and is_admin)


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------


@router.get("/stats", response_model=AdminStats)
async def get_stats(
    db: AsyncSession = Depends(get_async_session),
    _: User = Depends(require_admin),
) -> AdminStats:
    users_total = int((await db.scalar(select(func.count(User.id)))) or 0)

    by_role_rows = await db.execute(
        select(User.role, func.count(User.id)).group_by(User.role)
    )
    users_by_role: dict[str, int] = {r.value: 0 for r in UserRole}
    for role, count in by_role_rows:
        users_by_role[role.value if hasattr(role, "value") else str(role)] = int(count)

    problems_total = int((await db.scalar(select(func.count(Problem.id)))) or 0)
    problems_published = int(
        (await db.scalar(
            select(func.count(Problem.id)).where(Problem.published.is_(True))
        )) or 0
    )

    contests_total = int((await db.scalar(select(func.count(Contest.id)))) or 0)
    now = datetime.now(timezone.utc)
    contests_active = int(
        (await db.scalar(
            select(func.count(Contest.id)).where(
                Contest.start_at <= now,
                Contest.end_at >= now,
            )
        )) or 0
    )

    submissions_total = int((await db.scalar(select(func.count(Submission.id)))) or 0)
    cutoff = now - timedelta(hours=24)
    submissions_last_24h = int(
        (await db.scalar(
            select(func.count(Submission.id)).where(Submission.submitted_at >= cutoff)
        )) or 0
    )

    return AdminStats(
        users_total=users_total,
        users_by_role=users_by_role,
        problems_total=problems_total,
        problems_published=problems_published,
        contests_total=contests_total,
        contests_active=contests_active,
        submissions_total=submissions_total,
        submissions_last_24h=submissions_last_24h,
    )


@router.get("/users", response_model=list[AdminUserRead])
async def list_users(
    limit: Annotated[int, Query(ge=1, le=500)] = 200,
    offset: Annotated[int, Query(ge=0)] = 0,
    db: AsyncSession = Depends(get_async_session),
    _: User = Depends(require_admin),
) -> list[User]:
    stmt = select(User).order_by(User.id).offset(offset).limit(limit)
    rows = await db.execute(stmt)
    return list(rows.scalars().all())


@router.patch("/users/{user_id}", response_model=AdminUserRead)
async def update_user(
    user_id: int,
    body: AdminUserUpdate,
    db: AsyncSession = Depends(get_async_session),
    caller: User = Depends(require_admin),
) -> User:
    target = await db.get(User, user_id)
    if target is None:
        raise HTTPException(status_code=404, detail="User not found")

    is_self = target.id == caller.id

    # Self-protection: can't deactivate self.
    if is_self and body.is_active is False:
        raise HTTPException(
            status_code=400,
            detail="Cannot deactivate yourself",
        )

    # Self-protection: can't demote self via role change.
    if is_self and body.role is not None and body.role != UserRole.admin:
        raise HTTPException(
            status_code=400,
            detail="Cannot demote yourself; ask another admin",
        )

    # Last-admin protection: simulate the change and recount.
    if (body.role is not None and body.role != target.role) or body.is_active is not None:
        would_remain_admin = _would_remain_admin(
            target, new_role=body.role, new_active=body.is_active
        )
        if not would_remain_admin and (target.role == UserRole.admin or target.is_superuser):
            # This target is/was an admin and would no longer be one.
            other_admins = await _count_admins(db) - 1  # minus this user
            if other_admins <= 0:
                raise HTTPException(
                    status_code=400,
                    detail="Cannot demote or deactivate the last active admin",
                )

    if body.role is not None:
        target.role = body.role
        # Demoting a superuser via role change drops superuser too; that keeps
        # the visible role and capability in sync. Promoting via role doesn't
        # grant superuser automatically.
        if body.role != UserRole.admin:
            target.is_superuser = False
    if body.is_active is not None:
        target.is_active = body.is_active

    await db.commit()
    await db.refresh(target)
    return target


@router.get("/submissions", response_model=list[AdminSubmissionRow])
async def list_submissions(
    limit: Annotated[int, Query(ge=1, le=200)] = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
    db: AsyncSession = Depends(get_async_session),
    _: User = Depends(require_admin),
) -> list[AdminSubmissionRow]:
    stmt = (
        select(
            Submission.id,
            Submission.user_id,
            User.email,
            Submission.problem_id,
            Problem.slug,
            Submission.contest_id,
            Submission.status,
            Submission.score,
            Submission.submitted_at,
        )
        .join(User, User.id == Submission.user_id)
        .join(Problem, Problem.id == Submission.problem_id)
        .order_by(Submission.submitted_at.desc())
        .offset(offset)
        .limit(limit)
    )
    rows = await db.execute(stmt)
    out: list[AdminSubmissionRow] = []
    for sid, uid, email, pid, slug, cid, st, score, ts in rows:
        out.append(
            AdminSubmissionRow(
                id=sid,
                user_id=uid,
                user_email=email,
                problem_id=pid,
                problem_slug=slug,
                contest_id=cid,
                status=st,
                score=score,
                submitted_at=ts,
            )
        )
    return out
