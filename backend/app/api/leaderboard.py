"""Contest leaderboard endpoints.

Two shapes for the same data:

* ``GET  /contests/{slug}/leaderboard`` — one-shot JSON snapshot.
* ``GET  /contests/{slug}/leaderboard/stream`` — Server-Sent Events; pushes
  a refreshed snapshot every time a submission for the contest is judged
  (via Redis pub/sub), plus a keepalive comment every 15s.

Scoring respects the per-problem ``points`` weight assigned by the contest
owner — a submission scoring 90/100 on a problem worth 200 contributes
``(90/100) * 200 = 180`` to the participant's total. Falls back gracefully
when ``judge_spec.scoring.full_score`` is missing (default 100).
"""
from __future__ import annotations

import asyncio
import json
import logging
import os
from datetime import datetime, timezone
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.responses import StreamingResponse
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app import db as app_db
from app.core.security import UserManager, current_active_user, get_jwt_strategy
from app.db import get_async_session
from app.judge.events import subscribe_contest_updates
from app.models import Problem, Submission, SubmissionStatus, User
from app.models.contest import Contest, ContestProblem
from app.schemas.contest import Leaderboard, LeaderboardEntry

logger = logging.getLogger(__name__)

router = APIRouter()


def _problem_full_score(problem: Problem) -> float:
    """Look up the judge_spec's full_score (default 100) for normalising."""
    spec = problem.judge_spec if isinstance(problem.judge_spec, dict) else {}
    scoring = spec.get("scoring") if isinstance(spec, dict) else None
    if isinstance(scoring, dict):
        try:
            value = float(scoring.get("full_score", 100.0))
            return value if value > 0 else 100.0
        except (TypeError, ValueError):
            return 100.0
    return 100.0


async def _compute_leaderboard(db: AsyncSession, contest: Contest) -> Leaderboard:
    cp_rows = (
        await db.execute(
            select(ContestProblem.problem_id, ContestProblem.points)
            .where(ContestProblem.contest_id == contest.id)
        )
    ).all()
    points_by_problem: dict[int, int] = {pid: int(pts) for pid, pts in cp_rows}
    problem_ids = list(points_by_problem.keys())

    if not problem_ids:
        return Leaderboard(
            contest_id=contest.id,
            contest_slug=contest.slug,
            generated_at=datetime.now(timezone.utc),
            entries=[],
        )

    problems_result = await db.execute(select(Problem).where(Problem.id.in_(problem_ids)))
    full_score_by_problem = {p.id: _problem_full_score(p) for p in problems_result.scalars()}

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
        raw = float(best or 0.0)
        full = full_score_by_problem.get(int(problem_id), 100.0)
        contest_points = points_by_problem.get(int(problem_id), 0)
        weighted = (raw / full) * contest_points if full > 0 else 0.0
        per_user.setdefault(int(user_id), {})[int(problem_id)] = round(weighted, 4)

    if not per_user:
        return Leaderboard(
            contest_id=contest.id,
            contest_slug=contest.slug,
            generated_at=datetime.now(timezone.utc),
            entries=[],
        )

    users_result = await db.execute(select(User).where(User.id.in_(list(per_user.keys()))))
    users_by_id = {u.id: u for u in users_result.scalars().all()}

    aggregated: list[tuple[int, str, float, dict[int, float]]] = []
    for uid, by_problem in per_user.items():
        total = sum(by_problem.values())
        u = users_by_id.get(uid)
        display_name = (
            u.display_name if u and u.display_name else (u.email if u else f"user-{uid}")
        )
        aggregated.append((uid, display_name, total, by_problem))

    aggregated.sort(key=lambda e: e[2], reverse=True)
    entries = [
        LeaderboardEntry(
            rank=rank,
            user_id=uid,
            display_name=name,
            total_score=round(total, 4),
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


async def _get_contest_by_slug(db: AsyncSession, slug: str) -> Contest:
    contest = (
        await db.execute(select(Contest).where(Contest.slug == slug))
    ).scalar_one_or_none()
    if not contest:
        raise HTTPException(status_code=404, detail="Contest not found")
    return contest


@router.get("/{slug}/leaderboard", response_model=Leaderboard)
async def contest_leaderboard(
    slug: str,
    db: AsyncSession = Depends(get_async_session),
    user: User = Depends(current_active_user),
):
    contest = await _get_contest_by_slug(db, slug)
    return await _compute_leaderboard(db, contest)


async def _user_from_query_token(
    request: Request, token: str | None, db: AsyncSession
) -> User | None:
    """Validate a bearer token coming in as either a query string or header.

    EventSource doesn't send custom headers, so the SSE client passes the
    token as ``?token=...``. Returns ``None`` on any failure — the caller
    decides whether to 401. Uses the supplied session (which respects
    FastAPI dependency overrides in tests).
    """
    if not token:
        auth = request.headers.get("Authorization", "")
        if auth.lower().startswith("bearer "):
            token = auth[7:].strip()
    if not token:
        return None

    from fastapi_users.db import SQLAlchemyUserDatabase  # local import keeps API boot fast

    strategy = get_jwt_strategy()
    user_db = SQLAlchemyUserDatabase(db, User)
    user_manager = UserManager(user_db)
    try:
        return await strategy.read_token(token, user_manager)
    except Exception:  # noqa: BLE001
        return None


def _sse_pack(event: str, data: dict | str) -> bytes:
    body = data if isinstance(data, str) else json.dumps(data, default=str)
    return f"event: {event}\ndata: {body}\n\n".encode("utf-8")


@router.get("/{slug}/leaderboard/stream")
async def contest_leaderboard_stream(
    slug: str,
    request: Request,
    token: Annotated[str | None, Query()] = None,
    db: AsyncSession = Depends(get_async_session),
):
    user = await _user_from_query_token(request, token, db)
    if user is None or not user.is_active:
        raise HTTPException(status_code=401, detail="Authentication required")

    contest = await _get_contest_by_slug(db, slug)
    contest_id = contest.id

    async def event_stream():
        # Initial snapshot.
        try:
            async with app_db.async_session_maker() as session:
                contest = await session.get(Contest, contest_id)
                snapshot = await _compute_leaderboard(session, contest)
            yield _sse_pack("leaderboard", snapshot.model_dump(mode="json"))
        except Exception as e:  # noqa: BLE001
            logger.warning("leaderboard SSE initial snapshot failed: %s", e)

        # Tunable so tests can run fast without changing prod cadence.
        keepalive_interval = float(os.environ.get("OJ_SSE_KEEPALIVE_SECONDS", "15"))
        disconnect_poll = float(os.environ.get("OJ_SSE_DISCONNECT_POLL_SECONDS", "1"))

        async with subscribe_contest_updates(contest_id) as updates:
            keepalive_task = asyncio.create_task(asyncio.sleep(keepalive_interval))
            updates_task: asyncio.Task | None = None
            try:
                while True:
                    if updates_task is None:
                        updates_task = asyncio.create_task(updates.__anext__())

                    # Poll disconnects on a short timer so the connection
                    # closes promptly when the client goes away. Without this
                    # the server can hold open for ``keepalive_interval``
                    # after disconnect — bad for both clients and ASGI tests.
                    done, _ = await asyncio.wait(
                        {keepalive_task, updates_task},
                        return_when=asyncio.FIRST_COMPLETED,
                        timeout=disconnect_poll,
                    )

                    if await request.is_disconnected():
                        break

                    if not done:
                        # Disconnect-poll timeout fired but neither real task
                        # is ready yet — loop and re-check.
                        continue

                    if keepalive_task in done:
                        yield b": keepalive\n\n"
                        keepalive_task = asyncio.create_task(
                            asyncio.sleep(keepalive_interval)
                        )

                    if updates_task in done:
                        try:
                            updates_task.result()
                        except StopAsyncIteration:
                            break
                        except Exception as e:  # noqa: BLE001
                            # If the pub/sub source has died, exit the stream
                            # instead of spinning. EventSource will reconnect
                            # and we'll start clean from the snapshot.
                            logger.warning("leaderboard SSE source died: %s", e)
                            break
                        updates_task = None
                        try:
                            async with app_db.async_session_maker() as session:
                                contest = await session.get(Contest, contest_id)
                                snapshot = await _compute_leaderboard(session, contest)
                            yield _sse_pack(
                                "leaderboard", snapshot.model_dump(mode="json")
                            )
                        except Exception as e:  # noqa: BLE001
                            logger.warning("leaderboard SSE refresh failed: %s", e)
            finally:
                for t in (keepalive_task, updates_task):
                    if t and not t.done():
                        t.cancel()

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache, no-transform",
            "X-Accel-Buffering": "no",
            "Connection": "keep-alive",
        },
    )
