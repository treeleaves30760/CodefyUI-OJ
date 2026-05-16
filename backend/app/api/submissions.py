from datetime import datetime, timezone
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.core.security import current_active_user
from app.core.storage import ensure_dir, get_submission_dir
from app.db import get_async_session
from app.judge.queue import enqueue_judge
from app.models import Contest, Problem, Submission, User, UserRole
from app.models.contest import ContestParticipant
from app.models.submission import SubmissionStatus
from app.schemas.submission import (
    SubmissionCreate,
    SubmissionDetail,
    SubmissionListItem,
)

router = APIRouter()


@router.post("", response_model=SubmissionDetail, status_code=status.HTTP_201_CREATED)
async def create_submission(
    body: SubmissionCreate,
    db: AsyncSession = Depends(get_async_session),
    user: User = Depends(current_active_user),
):
    settings = get_settings()

    raw = body.graph_json
    if not isinstance(raw.get("nodes"), list) or not isinstance(raw.get("edges"), list):
        raise HTTPException(
            status_code=400,
            detail="graph_json must contain 'nodes' and 'edges' arrays",
        )
    if "custom:" in repr(raw):
        raise HTTPException(
            status_code=400,
            detail="Custom-typed nodes are not allowed in OJ submissions",
        )

    problem_result = await db.execute(
        select(Problem).where(Problem.slug == body.problem_slug)
    )
    problem = problem_result.scalar_one_or_none()
    if problem is None:
        raise HTTPException(status_code=404, detail="Problem not found")
    if not problem.published and user.role == UserRole.student and not user.is_superuser:
        raise HTTPException(status_code=404, detail="Problem not found")

    contest_id: int | None = None
    if body.contest_id is not None:
        contest = await db.get(Contest, body.contest_id)
        if contest is None:
            raise HTTPException(status_code=404, detail="Contest not found")
        now = datetime.now(timezone.utc)
        start = contest.start_at if contest.start_at.tzinfo else contest.start_at.replace(tzinfo=timezone.utc)
        end = contest.end_at if contest.end_at.tzinfo else contest.end_at.replace(tzinfo=timezone.utc)
        if not (start <= now <= end):
            raise HTTPException(status_code=400, detail="Contest is not active")
        part = await db.execute(
            select(ContestParticipant).where(
                ContestParticipant.contest_id == contest.id,
                ContestParticipant.user_id == user.id,
            )
        )
        if part.scalar_one_or_none() is None:
            raise HTTPException(status_code=403, detail="Not a participant in this contest")
        contest_id = contest.id

    submission = Submission(
        user_id=user.id,
        problem_id=problem.id,
        contest_id=contest_id,
        graph_json_path="",
        status=SubmissionStatus.queued,
    )
    db.add(submission)
    await db.commit()
    await db.refresh(submission)

    submission_dir = ensure_dir(get_submission_dir(submission.id))
    graph_path = submission_dir / "submission.json"

    import json

    graph_bytes = json.dumps(raw, ensure_ascii=False).encode("utf-8")
    if len(graph_bytes) > settings.submission_max_bytes:
        await db.delete(submission)
        await db.commit()
        raise HTTPException(
            status_code=413,
            detail=f"Submission exceeds {settings.submission_max_bytes} bytes",
        )

    graph_path.write_bytes(graph_bytes)
    submission.graph_json_path = str(graph_path.resolve())
    await db.commit()
    await db.refresh(submission)

    enqueue_judge(submission.id)
    await db.refresh(submission)

    return submission


@router.get("", response_model=list[SubmissionListItem])
async def list_my_submissions(
    problem_slug: Annotated[str | None, Query()] = None,
    contest_id: Annotated[int | None, Query()] = None,
    limit: Annotated[int, Query(ge=1, le=200)] = 50,
    db: AsyncSession = Depends(get_async_session),
    user: User = Depends(current_active_user),
):
    stmt = (
        select(Submission)
        .where(Submission.user_id == user.id)
        .order_by(desc(Submission.submitted_at))
        .limit(limit)
    )
    if problem_slug:
        prob = await db.execute(select(Problem).where(Problem.slug == problem_slug))
        problem = prob.scalar_one_or_none()
        if problem:
            stmt = stmt.where(Submission.problem_id == problem.id)
    if contest_id is not None:
        stmt = stmt.where(Submission.contest_id == contest_id)
    result = await db.execute(stmt)
    return list(result.scalars().all())


@router.get("/{submission_id}", response_model=SubmissionDetail)
async def get_submission(
    submission_id: int,
    db: AsyncSession = Depends(get_async_session),
    user: User = Depends(current_active_user),
):
    sub = await db.get(Submission, submission_id)
    if sub is None:
        raise HTTPException(status_code=404, detail="Submission not found")
    if sub.user_id != user.id and user.role not in (UserRole.teacher, UserRole.admin) and not user.is_superuser:
        raise HTTPException(status_code=403, detail="Forbidden")
    return sub
