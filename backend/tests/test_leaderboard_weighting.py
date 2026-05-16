"""Leaderboard scoring edge cases.

The contest leaderboard collapses (max submission per user per problem) and
weights each contribution by ``(score / problem.full_score) * contest_problem.points``.
These tests exercise the full grid:

- Weighting actually multiplies points (regression: original code ignored
  the contest's ``points`` column entirely and just summed raw scores).
- Different problems in the same contest can have different ``full_score``
  judge specs; the formula normalises correctly.
- Only ``judged`` submissions count — ``invalid`` / ``runtime_error`` /
  ``queued`` are excluded even if they carry a ``score`` value.
- Empty / sparse contests yield empty leaderboards rather than 500.
- Malformed ``judge_spec.scoring`` defaults to ``full_score=100`` and the
  endpoint stays up.
"""
from __future__ import annotations

import os

os.environ.setdefault("OJ_JUDGE_DISABLED", "true")
os.environ.setdefault("OJ_EVENTS_DISABLED", "true")

from datetime import datetime, timedelta, timezone

import pytest
import pytest_asyncio
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker

from app.models import Problem, Submission, SubmissionStatus, User
from app.models.contest import (
    Contest,
    ContestParticipant,
    ContestProblem,
    ContestVisibility,
)
from app.models.problem import ProblemDifficulty
from app.models.user import UserRole


async def _register_login(client: AsyncClient, email: str, pw: str = "password123") -> str:
    r = await client.post(
        "/api/auth/register",
        json={"email": email, "password": pw, "display_name": email.split("@")[0]},
    )
    assert r.status_code == 201, r.text
    r = await client.post(
        "/api/auth/jwt/login",
        data={"username": email, "password": pw},
    )
    return r.json()["access_token"]


async def _add_problem(
    session,
    *,
    slug: str,
    full_score: float = 100.0,
    method: str = "accuracy",
    author_id: int,
    judge_spec_override: dict | None = None,
) -> Problem:
    judge_spec = {
        "required_node_ids": ["__SUBMIT__"],
        "input_patches": [],
        "output_reads": [{"node_id": "__SUBMIT__", "port": "value", "save_as": "y_pred"}],
        "scoring": {
            "method": method,
            "target_output": "y_pred",
            "ground_truth": "{hidden_test_data}/y.csv",
            "threshold": 0.5,
            "full_score": full_score,
        },
    }
    if judge_spec_override is not None:
        judge_spec = judge_spec_override
    problem = Problem(
        slug=slug,
        title=slug,
        statement_md="",
        difficulty=ProblemDifficulty.easy,
        tags=[],
        starter_template_json={
            "nodes": [{"id": "__SUBMIT__", "type": "Print", "data": {"params": {}}}],
            "edges": [],
        },
        judge_spec=judge_spec,
        time_limit_seconds=60,
        memory_limit_mb=1024,
        published=True,
        created_by_user_id=author_id,
    )
    session.add(problem)
    await session.commit()
    await session.refresh(problem)
    return problem


@pytest_asyncio.fixture
async def teacher_user(client: AsyncClient, test_engine) -> tuple[str, int]:
    await _register_login(client, "lb-teacher@codefy.dev")
    sm = async_sessionmaker(test_engine, expire_on_commit=False)
    async with sm() as session:
        from sqlalchemy import update

        await session.execute(
            update(User).where(User.email == "lb-teacher@codefy.dev").values(role=UserRole.teacher)
        )
        await session.commit()
        u = (
            await session.execute(select(User).where(User.email == "lb-teacher@codefy.dev"))
        ).scalar_one()
    r = await client.post(
        "/api/auth/jwt/login",
        data={"username": "lb-teacher@codefy.dev", "password": "password123"},
    )
    return r.json()["access_token"], u.id


async def _make_contest(
    session,
    *,
    slug: str,
    teacher_id: int,
    problems: list[tuple[Problem, int]],
) -> Contest:
    now = datetime.now(timezone.utc)
    contest = Contest(
        slug=slug,
        title=slug,
        description_md="",
        start_at=now - timedelta(hours=1),
        end_at=now + timedelta(hours=2),
        visibility=ContestVisibility.public,
        created_by_user_id=teacher_id,
    )
    session.add(contest)
    await session.flush()
    for order, (p, pts) in enumerate(problems):
        session.add(
            ContestProblem(
                contest_id=contest.id, problem_id=p.id, points=pts, display_order=order
            )
        )
    await session.commit()
    await session.refresh(contest)
    return contest


# ---------------------------------------------------------------------------
# Weighting math.
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_weighted_score_multiplies_points(client, teacher_user, test_engine):
    token, teacher_id = teacher_user
    sm = async_sessionmaker(test_engine, expire_on_commit=False)
    async with sm() as session:
        p = await _add_problem(session, slug="wp-1", full_score=100.0, author_id=teacher_id)
        contest = await _make_contest(
            session, slug="wp-1-contest", teacher_id=teacher_id, problems=[(p, 250)]
        )

    student_token = await _register_login(client, "wp1-alice@codefy.dev")
    async with sm() as session:
        u = (
            await session.execute(select(User).where(User.email == "wp1-alice@codefy.dev"))
        ).scalar_one()
        session.add(
            Submission(
                user_id=u.id,
                problem_id=p.id,
                contest_id=contest.id,
                graph_json_path="",
                status=SubmissionStatus.judged,
                score=80.0,  # 80/100 → 0.8 * 250 = 200
            )
        )
        await session.commit()

    r = await client.get(
        f"/api/contests/{contest.slug}/leaderboard",
        headers={"Authorization": f"Bearer {student_token}"},
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["entries"][0]["total_score"] == 200.0
    assert body["entries"][0]["per_problem"][str(p.id)] == 200.0


@pytest.mark.asyncio
async def test_weighted_score_normalises_by_full_score(client, teacher_user, test_engine):
    """A problem with full_score=50 and a 25/50 submission should weight 0.5×points."""
    token, teacher_id = teacher_user
    sm = async_sessionmaker(test_engine, expire_on_commit=False)
    async with sm() as session:
        p = await _add_problem(session, slug="wp-norm", full_score=50.0, author_id=teacher_id)
        contest = await _make_contest(
            session, slug="wp-norm-contest", teacher_id=teacher_id, problems=[(p, 400)]
        )

    student_token = await _register_login(client, "wp-norm-alice@codefy.dev")
    async with sm() as session:
        u = (
            await session.execute(select(User).where(User.email == "wp-norm-alice@codefy.dev"))
        ).scalar_one()
        session.add(
            Submission(
                user_id=u.id,
                problem_id=p.id,
                contest_id=contest.id,
                graph_json_path="",
                status=SubmissionStatus.judged,
                score=25.0,  # half of full_score → 0.5 * 400 = 200
            )
        )
        await session.commit()

    r = await client.get(
        f"/api/contests/{contest.slug}/leaderboard",
        headers={"Authorization": f"Bearer {student_token}"},
    )
    assert r.json()["entries"][0]["total_score"] == 200.0


@pytest.mark.asyncio
async def test_weighted_score_takes_max_per_user_per_problem(
    client, teacher_user, test_engine
):
    """Submitting twice keeps only the better attempt per (user, problem)."""
    token, teacher_id = teacher_user
    sm = async_sessionmaker(test_engine, expire_on_commit=False)
    async with sm() as session:
        p = await _add_problem(session, slug="wp-max", author_id=teacher_id)
        contest = await _make_contest(
            session, slug="wp-max-contest", teacher_id=teacher_id, problems=[(p, 100)]
        )

    student_token = await _register_login(client, "wp-max-alice@codefy.dev")
    async with sm() as session:
        u = (
            await session.execute(select(User).where(User.email == "wp-max-alice@codefy.dev"))
        ).scalar_one()
        for s in (40.0, 60.0, 30.0):
            session.add(
                Submission(
                    user_id=u.id, problem_id=p.id, contest_id=contest.id,
                    graph_json_path="", status=SubmissionStatus.judged, score=s,
                )
            )
        await session.commit()

    r = await client.get(
        f"/api/contests/{contest.slug}/leaderboard",
        headers={"Authorization": f"Bearer {student_token}"},
    )
    assert r.json()["entries"][0]["total_score"] == 60.0


@pytest.mark.asyncio
async def test_unjudged_submissions_are_ignored(client, teacher_user, test_engine):
    token, teacher_id = teacher_user
    sm = async_sessionmaker(test_engine, expire_on_commit=False)
    async with sm() as session:
        p = await _add_problem(session, slug="wp-skip", author_id=teacher_id)
        contest = await _make_contest(
            session, slug="wp-skip-contest", teacher_id=teacher_id, problems=[(p, 100)]
        )

    student_token = await _register_login(client, "wp-skip-alice@codefy.dev")
    async with sm() as session:
        u = (
            await session.execute(select(User).where(User.email == "wp-skip-alice@codefy.dev"))
        ).scalar_one()
        # Higher score on a non-judged submission must NOT win.
        session.add_all([
            Submission(
                user_id=u.id, problem_id=p.id, contest_id=contest.id,
                graph_json_path="", status=SubmissionStatus.runtime_error, score=99.0,
            ),
            Submission(
                user_id=u.id, problem_id=p.id, contest_id=contest.id,
                graph_json_path="", status=SubmissionStatus.invalid, score=88.0,
            ),
            Submission(
                user_id=u.id, problem_id=p.id, contest_id=contest.id,
                graph_json_path="", status=SubmissionStatus.queued, score=None,
            ),
            Submission(
                user_id=u.id, problem_id=p.id, contest_id=contest.id,
                graph_json_path="", status=SubmissionStatus.judged, score=42.0,
            ),
        ])
        await session.commit()

    r = await client.get(
        f"/api/contests/{contest.slug}/leaderboard",
        headers={"Authorization": f"Bearer {student_token}"},
    )
    assert r.json()["entries"][0]["total_score"] == 42.0


@pytest.mark.asyncio
async def test_multiple_problems_aggregate(client, teacher_user, test_engine):
    token, teacher_id = teacher_user
    sm = async_sessionmaker(test_engine, expire_on_commit=False)
    async with sm() as session:
        p1 = await _add_problem(session, slug="wp-multi-a", full_score=100.0, author_id=teacher_id)
        p2 = await _add_problem(session, slug="wp-multi-b", full_score=200.0, author_id=teacher_id)
        contest = await _make_contest(
            session,
            slug="wp-multi-contest",
            teacher_id=teacher_id,
            problems=[(p1, 100), (p2, 300)],
        )

    student_token = await _register_login(client, "wp-multi-alice@codefy.dev")
    async with sm() as session:
        u = (
            await session.execute(select(User).where(User.email == "wp-multi-alice@codefy.dev"))
        ).scalar_one()
        session.add(
            Submission(
                user_id=u.id, problem_id=p1.id, contest_id=contest.id,
                graph_json_path="", status=SubmissionStatus.judged, score=50.0,
            )
        )
        session.add(
            Submission(
                user_id=u.id, problem_id=p2.id, contest_id=contest.id,
                graph_json_path="", status=SubmissionStatus.judged, score=100.0,
            )
        )
        await session.commit()

    r = await client.get(
        f"/api/contests/{contest.slug}/leaderboard",
        headers={"Authorization": f"Bearer {student_token}"},
    )
    entry = r.json()["entries"][0]
    # (50/100)*100 + (100/200)*300 = 50 + 150 = 200
    assert entry["total_score"] == 200.0
    assert entry["per_problem"][str(p1.id)] == 50.0
    assert entry["per_problem"][str(p2.id)] == 150.0


@pytest.mark.asyncio
async def test_ranking_orders_by_total_desc(client, teacher_user, test_engine):
    token, teacher_id = teacher_user
    sm = async_sessionmaker(test_engine, expire_on_commit=False)
    async with sm() as session:
        p = await _add_problem(session, slug="wp-rank", author_id=teacher_id)
        contest = await _make_contest(
            session, slug="wp-rank-contest", teacher_id=teacher_id, problems=[(p, 100)]
        )

    alice = await _register_login(client, "wp-rank-alice@codefy.dev")
    bob = await _register_login(client, "wp-rank-bob@codefy.dev")
    carol = await _register_login(client, "wp-rank-carol@codefy.dev")

    async with sm() as session:
        users = (
            await session.execute(
                select(User).where(User.email.in_(
                    [
                        "wp-rank-alice@codefy.dev",
                        "wp-rank-bob@codefy.dev",
                        "wp-rank-carol@codefy.dev",
                    ]
                ))
            )
        ).scalars().all()
        by_email = {u.email: u for u in users}
        for email, score in [
            ("wp-rank-alice@codefy.dev", 75.0),
            ("wp-rank-bob@codefy.dev", 99.0),
            ("wp-rank-carol@codefy.dev", 50.0),
        ]:
            session.add(
                Submission(
                    user_id=by_email[email].id, problem_id=p.id, contest_id=contest.id,
                    graph_json_path="", status=SubmissionStatus.judged, score=score,
                )
            )
        await session.commit()

    r = await client.get(
        f"/api/contests/{contest.slug}/leaderboard",
        headers={"Authorization": f"Bearer {alice}"},
    )
    entries = r.json()["entries"]
    assert [(e["display_name"], e["rank"]) for e in entries] == [
        ("wp-rank-bob", 1),
        ("wp-rank-alice", 2),
        ("wp-rank-carol", 3),
    ]


# ---------------------------------------------------------------------------
# Defensive edge cases.
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_contest_with_no_problems_returns_empty(client, teacher_user, test_engine):
    token, teacher_id = teacher_user
    sm = async_sessionmaker(test_engine, expire_on_commit=False)
    async with sm() as session:
        await _make_contest(
            session, slug="wp-empty", teacher_id=teacher_id, problems=[]
        )
    r = await client.get(
        "/api/contests/wp-empty/leaderboard",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert r.status_code == 200
    assert r.json()["entries"] == []


@pytest.mark.asyncio
async def test_no_submissions_yields_empty(client, teacher_user, test_engine):
    token, teacher_id = teacher_user
    sm = async_sessionmaker(test_engine, expire_on_commit=False)
    async with sm() as session:
        p = await _add_problem(session, slug="wp-nosub", author_id=teacher_id)
        await _make_contest(
            session, slug="wp-nosub-contest", teacher_id=teacher_id, problems=[(p, 100)]
        )

    r = await client.get(
        "/api/contests/wp-nosub-contest/leaderboard",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert r.json()["entries"] == []


@pytest.mark.asyncio
async def test_missing_full_score_defaults_to_100(client, teacher_user, test_engine):
    """A judge_spec stored without scoring.full_score must not 500 the API."""
    token, teacher_id = teacher_user
    sm = async_sessionmaker(test_engine, expire_on_commit=False)
    async with sm() as session:
        p = await _add_problem(
            session,
            slug="wp-malformed",
            author_id=teacher_id,
            judge_spec_override={"scoring": {}},  # no full_score, no method
        )
        contest = await _make_contest(
            session, slug="wp-malformed-c", teacher_id=teacher_id, problems=[(p, 100)]
        )

    student_token = await _register_login(client, "wp-malformed-alice@codefy.dev")
    async with sm() as session:
        u = (
            await session.execute(
                select(User).where(User.email == "wp-malformed-alice@codefy.dev")
            )
        ).scalar_one()
        session.add(
            Submission(
                user_id=u.id, problem_id=p.id, contest_id=contest.id,
                graph_json_path="", status=SubmissionStatus.judged, score=70.0,
            )
        )
        await session.commit()

    r = await client.get(
        f"/api/contests/{contest.slug}/leaderboard",
        headers={"Authorization": f"Bearer {student_token}"},
    )
    assert r.status_code == 200
    # full_score defaults to 100 → (70/100)*100 = 70
    assert r.json()["entries"][0]["total_score"] == 70.0


@pytest.mark.asyncio
async def test_zero_or_negative_full_score_defaults_safe(client, teacher_user, test_engine):
    """A nonsense full_score=0 should not divide-by-zero — defaults to 100."""
    from app.api.leaderboard import _problem_full_score

    class FakeProblem:
        judge_spec = {"scoring": {"full_score": 0}}

    assert _problem_full_score(FakeProblem()) == 100.0
    FakeProblem.judge_spec = {"scoring": {"full_score": -5}}
    assert _problem_full_score(FakeProblem()) == 100.0
    FakeProblem.judge_spec = None  # not a dict at all
    assert _problem_full_score(FakeProblem()) == 100.0
    FakeProblem.judge_spec = {"scoring": {"full_score": "not a number"}}
    assert _problem_full_score(FakeProblem()) == 100.0


@pytest.mark.asyncio
async def test_unknown_slug_returns_404(client, teacher_user):
    token, _ = teacher_user
    r = await client.get(
        "/api/contests/does-not-exist/leaderboard",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert r.status_code == 404


@pytest.mark.asyncio
async def test_leaderboard_requires_auth(client, teacher_user):
    r = await client.get("/api/contests/anything/leaderboard")
    assert r.status_code == 401
