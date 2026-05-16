from datetime import datetime, timezone
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import desc, func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.permissions import require_teacher
from app.core.security import current_active_user
from app.db import get_async_session
from app.models import Problem, User
from app.models.contest import (
    Contest,
    ContestParticipant,
    ContestProblem,
)
from app.schemas.contest import (
    ContestCreate,
    ContestListItem,
    ContestProblemEntry,
    ContestProblemRead,
    ContestRead,
    ContestRuntimeStatus,
    ContestUpdate,
)

router = APIRouter()


def _runtime_status(contest: Contest, now: datetime | None = None) -> ContestRuntimeStatus:
    now = now or datetime.now(timezone.utc)
    if now < _as_aware(contest.start_at):
        return "upcoming"
    if now <= _as_aware(contest.end_at):
        return "active"
    return "past"


def _as_aware(dt: datetime) -> datetime:
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt


async def _build_problem_entries(
    db: AsyncSession, contest_id: int
) -> list[ContestProblemRead]:
    stmt = (
        select(ContestProblem, Problem.slug, Problem.title)
        .join(Problem, ContestProblem.problem_id == Problem.id)
        .where(ContestProblem.contest_id == contest_id)
        .order_by(ContestProblem.display_order, ContestProblem.problem_id)
    )
    rows = await db.execute(stmt)
    return [
        ContestProblemRead(
            problem_id=cp.problem_id,
            problem_slug=slug,
            problem_title=title,
            points=cp.points,
            display_order=cp.display_order,
        )
        for cp, slug, title in rows
    ]


async def _participant_count(db: AsyncSession, contest_id: int) -> int:
    stmt = select(func.count()).select_from(ContestParticipant).where(
        ContestParticipant.contest_id == contest_id
    )
    return int((await db.execute(stmt)).scalar_one() or 0)


async def _is_participant(db: AsyncSession, contest_id: int, user_id: int) -> bool:
    stmt = select(ContestParticipant).where(
        ContestParticipant.contest_id == contest_id,
        ContestParticipant.user_id == user_id,
    )
    return (await db.execute(stmt)).scalar_one_or_none() is not None


async def _get_or_404(db: AsyncSession, contest_id: int) -> Contest:
    contest = await db.get(Contest, contest_id)
    if not contest:
        raise HTTPException(status_code=404, detail="Contest not found")
    return contest


async def _resolve_problems(
    db: AsyncSession, entries: list[ContestProblemEntry]
) -> list[tuple[ContestProblemEntry, Problem]]:
    if not entries:
        return []
    slugs = [e.problem_slug for e in entries]
    result = await db.execute(select(Problem).where(Problem.slug.in_(slugs)))
    by_slug = {p.slug: p for p in result.scalars().all()}
    missing = [s for s in slugs if s not in by_slug]
    if missing:
        raise HTTPException(status_code=400, detail=f"Unknown problem slugs: {missing}")
    return [(entry, by_slug[entry.problem_slug]) for entry in entries]


@router.get("", response_model=list[ContestListItem])
async def list_contests(
    runtime_status: Annotated[
        ContestRuntimeStatus | None, Query(alias="status")
    ] = None,
    limit: Annotated[int, Query(ge=1, le=200)] = 100,
    db: AsyncSession = Depends(get_async_session),
    user: User = Depends(current_active_user),
):
    stmt = select(Contest).order_by(desc(Contest.start_at)).limit(limit)
    result = await db.execute(stmt)
    contests = list(result.scalars().all())

    counts: dict[int, int] = {}
    if contests:
        cnt_stmt = (
            select(ContestProblem.contest_id, func.count())
            .where(ContestProblem.contest_id.in_([c.id for c in contests]))
            .group_by(ContestProblem.contest_id)
        )
        for cid, n in await db.execute(cnt_stmt):
            counts[cid] = n

    out: list[ContestListItem] = []
    for c in contests:
        rs = _runtime_status(c)
        if runtime_status and rs != runtime_status:
            continue
        out.append(
            ContestListItem(
                id=c.id,
                slug=c.slug,
                title=c.title,
                start_at=c.start_at,
                end_at=c.end_at,
                visibility=c.visibility,
                runtime_status=rs,
                problem_count=counts.get(c.id, 0),
            )
        )
    return out


@router.post("", response_model=ContestRead, status_code=status.HTTP_201_CREATED)
async def create_contest(
    body: ContestCreate,
    db: AsyncSession = Depends(get_async_session),
    user: User = Depends(require_teacher),
):
    existing = await db.execute(select(Contest).where(Contest.slug == body.slug))
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=409, detail="Slug already exists")

    resolved = await _resolve_problems(db, body.problems)

    contest = Contest(
        slug=body.slug,
        title=body.title,
        description_md=body.description_md,
        start_at=body.start_at,
        end_at=body.end_at,
        visibility=body.visibility,
        created_by_user_id=user.id,
    )
    db.add(contest)
    await db.flush()

    for entry, problem in resolved:
        db.add(
            ContestProblem(
                contest_id=contest.id,
                problem_id=problem.id,
                points=entry.points,
                display_order=entry.display_order,
            )
        )

    await db.commit()
    await db.refresh(contest)
    return await _to_read(db, contest, user)


@router.get("/{slug}", response_model=ContestRead)
async def get_contest(
    slug: str,
    db: AsyncSession = Depends(get_async_session),
    user: User = Depends(current_active_user),
):
    result = await db.execute(select(Contest).where(Contest.slug == slug))
    contest = result.scalar_one_or_none()
    if not contest:
        raise HTTPException(status_code=404, detail="Contest not found")
    return await _to_read(db, contest, user)


@router.put("/{slug}", response_model=ContestRead)
async def update_contest(
    slug: str,
    body: ContestUpdate,
    db: AsyncSession = Depends(get_async_session),
    user: User = Depends(require_teacher),
):
    result = await db.execute(select(Contest).where(Contest.slug == slug))
    contest = result.scalar_one_or_none()
    if not contest:
        raise HTTPException(status_code=404, detail="Contest not found")
    updates = body.model_dump(exclude_unset=True)
    for key, value in updates.items():
        setattr(contest, key, value)
    if contest.end_at <= contest.start_at:
        raise HTTPException(status_code=400, detail="end_at must be after start_at")
    await db.commit()
    await db.refresh(contest)
    return await _to_read(db, contest, user)


@router.delete("/{slug}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_contest(
    slug: str,
    db: AsyncSession = Depends(get_async_session),
    user: User = Depends(require_teacher),
):
    result = await db.execute(select(Contest).where(Contest.slug == slug))
    contest = result.scalar_one_or_none()
    if not contest:
        raise HTTPException(status_code=404, detail="Contest not found")
    await db.delete(contest)
    await db.commit()


@router.post("/{slug}/problems", response_model=ContestRead)
async def add_contest_problem(
    slug: str,
    entry: ContestProblemEntry,
    db: AsyncSession = Depends(get_async_session),
    user: User = Depends(require_teacher),
):
    result = await db.execute(select(Contest).where(Contest.slug == slug))
    contest = result.scalar_one_or_none()
    if not contest:
        raise HTTPException(status_code=404, detail="Contest not found")

    pr = await db.execute(select(Problem).where(Problem.slug == entry.problem_slug))
    problem = pr.scalar_one_or_none()
    if not problem:
        raise HTTPException(status_code=400, detail=f"Unknown problem: {entry.problem_slug}")

    existing = await db.execute(
        select(ContestProblem).where(
            ContestProblem.contest_id == contest.id,
            ContestProblem.problem_id == problem.id,
        )
    )
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=409, detail="Problem already in contest")

    db.add(
        ContestProblem(
            contest_id=contest.id,
            problem_id=problem.id,
            points=entry.points,
            display_order=entry.display_order,
        )
    )
    await db.commit()
    await db.refresh(contest)
    return await _to_read(db, contest, user)


@router.delete("/{slug}/problems/{problem_slug}", status_code=status.HTTP_204_NO_CONTENT)
async def remove_contest_problem(
    slug: str,
    problem_slug: str,
    db: AsyncSession = Depends(get_async_session),
    user: User = Depends(require_teacher),
):
    cr = await db.execute(select(Contest).where(Contest.slug == slug))
    contest = cr.scalar_one_or_none()
    if not contest:
        raise HTTPException(status_code=404, detail="Contest not found")
    pr = await db.execute(select(Problem).where(Problem.slug == problem_slug))
    problem = pr.scalar_one_or_none()
    if not problem:
        raise HTTPException(status_code=404, detail="Problem not found")
    cp_result = await db.execute(
        select(ContestProblem).where(
            ContestProblem.contest_id == contest.id,
            ContestProblem.problem_id == problem.id,
        )
    )
    cp = cp_result.scalar_one_or_none()
    if not cp:
        raise HTTPException(status_code=404, detail="Problem not in contest")
    await db.delete(cp)
    await db.commit()


@router.post("/{slug}/join", response_model=ContestRead)
async def join_contest(
    slug: str,
    db: AsyncSession = Depends(get_async_session),
    user: User = Depends(current_active_user),
):
    result = await db.execute(select(Contest).where(Contest.slug == slug))
    contest = result.scalar_one_or_none()
    if not contest:
        raise HTTPException(status_code=404, detail="Contest not found")

    already = await _is_participant(db, contest.id, user.id)
    if not already:
        db.add(ContestParticipant(contest_id=contest.id, user_id=user.id))
        await db.commit()
        await db.refresh(contest)
    return await _to_read(db, contest, user)


async def _to_read(db: AsyncSession, contest: Contest, user: User) -> ContestRead:
    problems = await _build_problem_entries(db, contest.id)
    participants = await _participant_count(db, contest.id)
    joined = await _is_participant(db, contest.id, user.id)
    return ContestRead(
        id=contest.id,
        slug=contest.slug,
        title=contest.title,
        description_md=contest.description_md,
        start_at=contest.start_at,
        end_at=contest.end_at,
        visibility=contest.visibility,
        created_by_user_id=contest.created_by_user_id,
        created_at=contest.created_at,
        updated_at=contest.updated_at,
        runtime_status=_runtime_status(contest),
        problems=problems,
        participant_count=participants,
        joined=joined,
    )
