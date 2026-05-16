from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import current_active_user
from app.db import get_async_session
from app.models import Submission, SubmissionStatus, User
from app.models.contest import Contest, ContestProblem
from app.schemas.contest import Leaderboard, LeaderboardEntry

router = APIRouter()


@router.get("/{slug}/leaderboard", response_model=Leaderboard)
async def contest_leaderboard(
    slug: str,
    db: AsyncSession = Depends(get_async_session),
    user: User = Depends(current_active_user),
):
    contest_result = await db.execute(select(Contest).where(Contest.slug == slug))
    contest = contest_result.scalar_one_or_none()
    if not contest:
        raise HTTPException(status_code=404, detail="Contest not found")

    problem_ids_result = await db.execute(
        select(ContestProblem.problem_id).where(ContestProblem.contest_id == contest.id)
    )
    problem_ids = [row[0] for row in problem_ids_result]

    if not problem_ids:
        return Leaderboard(
            contest_id=contest.id,
            contest_slug=contest.slug,
            generated_at=datetime.now(timezone.utc),
            entries=[],
        )

    scores_stmt = (
        select(
            Submission.user_id,
            Submission.problem_id,
            func.max(Submission.score).label("best"),
        )
        .where(Submission.contest_id == contest.id)
        .where(Submission.status == SubmissionStatus.judged)
        .where(Submission.problem_id.in_(problem_ids))
        .group_by(Submission.user_id, Submission.problem_id)
    )
    rows = await db.execute(scores_stmt)
    per_user: dict[int, dict[int, float]] = {}
    for user_id, problem_id, best in rows:
        per_user.setdefault(int(user_id), {})[int(problem_id)] = float(best or 0.0)

    if not per_user:
        return Leaderboard(
            contest_id=contest.id,
            contest_slug=contest.slug,
            generated_at=datetime.now(timezone.utc),
            entries=[],
        )

    user_ids = list(per_user.keys())
    users_result = await db.execute(select(User).where(User.id.in_(user_ids)))
    users_by_id = {u.id: u for u in users_result.scalars().all()}

    aggregated = []
    for uid, by_problem in per_user.items():
        total = sum(by_problem.values())
        u = users_by_id.get(uid)
        display_name = (u.display_name if u and u.display_name else (u.email if u else f"user-{uid}"))
        aggregated.append((uid, display_name, total, by_problem))

    aggregated.sort(key=lambda e: e[2], reverse=True)
    entries = [
        LeaderboardEntry(
            rank=rank,
            user_id=uid,
            display_name=name,
            total_score=total,
            per_problem=by_problem,
        )
        for rank, (uid, name, total, by_problem) in enumerate(aggregated, start=1)
    ]

    return Leaderboard(
        contest_id=contest.id,
        contest_slug=contest.slug,
        generated_at=datetime.now(timezone.utc),
        entries=entries,
    )
