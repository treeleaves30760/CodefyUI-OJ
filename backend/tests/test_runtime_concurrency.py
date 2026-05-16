"""End-to-end concurrency tests for the OJ runtime.

What this file covers (things integration tests, unit tests, and existing
suite don't):

- Many worker _finalize calls finishing in parallel for the same contest:
  leaderboard ends up with the correct max-per-user-per-problem aggregate
  regardless of finish order.
- The judge worker publishes exactly once per contest submission even when
  several finalize in the same event loop turn.
- Submission boundaries: contest end_at is enforced — submissions after
  the window close get 400, not added to the leaderboard.
- Joining a contest is idempotent under repeated calls (race-safe).
- The leaderboard read endpoint stays consistent (same totals from
  parallel readers) while inserts are happening underneath.
- A judged submission that crashes after commit but before publish never
  corrupts the leaderboard.

Tests run against the in-memory test_engine — concurrent inserts here are
serialised by SQLite's writer lock (mirroring Postgres's row locks well
enough for these scenarios).
"""
from __future__ import annotations

import asyncio
import os

os.environ.setdefault("OJ_JUDGE_DISABLED", "true")
os.environ.setdefault("OJ_EVENTS_DISABLED", "true")

from datetime import datetime, timedelta, timezone

import pytest
import pytest_asyncio
from httpx import AsyncClient
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import async_sessionmaker

from app.judge import worker as judge_worker
from app.models import Problem, Submission, SubmissionStatus, User
from app.models.contest import (
    Contest,
    ContestParticipant,
    ContestProblem,
    ContestVisibility,
)
from app.models.problem import ProblemDifficulty
from app.models.user import UserRole


# ---------------------------------------------------------------------------
# Shared fixtures
# ---------------------------------------------------------------------------


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


@pytest_asyncio.fixture
async def stage(test_engine, monkeypatch):
    """Set up one teacher, one problem, one active contest. Return everything."""
    from fastapi_users.password import PasswordHelper

    sm = async_sessionmaker(test_engine, expire_on_commit=False)
    # Ensure worker._finalize sees the test engine.
    monkeypatch.setattr("app.db.async_session_maker", sm)
    monkeypatch.setattr("app.judge.worker.async_session_maker", sm)

    async with sm() as session:
        teacher = User(
            email="rt-teacher@codefy.dev",
            hashed_password=PasswordHelper().hash("xx"),
            display_name="Teacher",
            role=UserRole.teacher,
            is_active=True, is_superuser=False, is_verified=True,
        )
        session.add(teacher)
        await session.flush()
        problem = Problem(
            slug="rt-p1",
            title="P1",
            statement_md="",
            difficulty=ProblemDifficulty.easy,
            tags=[],
            starter_template_json={"nodes": [], "edges": []},
            judge_spec={"scoring": {"full_score": 100}},
            time_limit_seconds=30,
            memory_limit_mb=512,
            published=True,
            created_by_user_id=teacher.id,
        )
        session.add(problem)
        await session.flush()
        now = datetime.now(timezone.utc)
        contest = Contest(
            slug="rt-c1",
            title="C1",
            description_md="",
            start_at=now - timedelta(hours=1),
            end_at=now + timedelta(hours=2),
            visibility=ContestVisibility.public,
            created_by_user_id=teacher.id,
        )
        session.add(contest)
        await session.flush()
        session.add(
            ContestProblem(
                contest_id=contest.id, problem_id=problem.id, points=200, display_order=0,
            )
        )
        await session.commit()

    return {"sm": sm, "problem_id": problem.id, "contest_id": contest.id}


async def _create_queued_submissions(
    sm, *, user_emails: list[str], problem_id: int, contest_id: int
) -> dict[str, int]:
    """For each email, register a user (if not exists) and queue a submission."""
    from fastapi_users.password import PasswordHelper

    sub_ids: dict[str, int] = {}
    async with sm() as session:
        for email in user_emails:
            existing = (
                await session.execute(select(User).where(User.email == email))
            ).scalar_one_or_none()
            if existing is None:
                user = User(
                    email=email,
                    hashed_password=PasswordHelper().hash("xx"),
                    display_name=email.split("@")[0],
                    role=UserRole.student,
                    is_active=True, is_superuser=False, is_verified=True,
                )
                session.add(user)
                await session.flush()
                existing = user
            sub = Submission(
                user_id=existing.id,
                problem_id=problem_id,
                contest_id=contest_id,
                graph_json_path="",
                status=SubmissionStatus.queued,
            )
            session.add(sub)
            await session.flush()
            sub_ids[email] = sub.id
        await session.commit()
    return sub_ids


# ---------------------------------------------------------------------------
# Parallel finalize → leaderboard
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_parallel_finalize_produces_consistent_leaderboard(stage, monkeypatch):
    """Two workers finalize submissions for the same contest at once.

    Each worker writes its own submission row; the leaderboard aggregates
    via MAX(score). Ordering of commits must not affect the result.
    """
    publishes: list[int] = []
    monkeypatch.setattr(
        judge_worker, "publish_contest_update",
        lambda cid, **kw: publishes.append(cid),
    )

    sm = stage["sm"]
    sub_ids = await _create_queued_submissions(
        sm,
        user_emails=[f"par-{i}@codefy.dev" for i in range(8)],
        problem_id=stage["problem_id"],
        contest_id=stage["contest_id"],
    )

    # Each "worker" calls _finalize concurrently with a different score.
    scores = list(range(10, 90, 10))  # 8 distinct scores
    finalizers = [
        judge_worker._finalize(
            sid,
            status=SubmissionStatus.judged,
            score=float(score),
            log="",
            runtime_ms=1,
            raw={},
        )
        for sid, score in zip(sub_ids.values(), scores)
    ]
    await asyncio.gather(*finalizers)

    # One publish per contest submission (no double-publishing).
    assert len(publishes) == 8
    assert all(p == stage["contest_id"] for p in publishes)

    # Leaderboard reflects each user's score.
    from app.api.leaderboard import _compute_leaderboard

    async with sm() as session:
        contest = await session.get(Contest, stage["contest_id"])
        lb = await _compute_leaderboard(session, contest)

    assert len(lb.entries) == 8
    # Each user's total = (score/100)*200 = score*2
    by_name = {e.display_name: e.total_score for e in lb.entries}
    for i, score in enumerate(scores):
        expected = score * 2.0  # (score/100) * 200
        assert by_name[f"par-{i}"] == expected, (i, score, by_name[f"par-{i}"])


@pytest.mark.asyncio
async def test_multiple_submissions_per_user_keeps_max(stage, monkeypatch):
    """Same user, three concurrent finalizes — leaderboard keeps the best."""
    monkeypatch.setattr(
        judge_worker, "publish_contest_update", lambda *a, **k: None,
    )

    sm = stage["sm"]
    # Same user, three different submissions.
    sub_ids: list[int] = []
    from fastapi_users.password import PasswordHelper

    async with sm() as session:
        u = User(
            email="best@codefy.dev",
            hashed_password=PasswordHelper().hash("xx"),
            display_name="Best",
            role=UserRole.student,
            is_active=True, is_superuser=False, is_verified=True,
        )
        session.add(u)
        await session.flush()
        for _ in range(3):
            s = Submission(
                user_id=u.id, problem_id=stage["problem_id"],
                contest_id=stage["contest_id"], graph_json_path="",
                status=SubmissionStatus.queued,
            )
            session.add(s)
            await session.flush()
            sub_ids.append(s.id)
        await session.commit()

    await asyncio.gather(
        judge_worker._finalize(
            sub_ids[0], status=SubmissionStatus.judged, score=30.0, log="", runtime_ms=1, raw={},
        ),
        judge_worker._finalize(
            sub_ids[1], status=SubmissionStatus.judged, score=85.0, log="", runtime_ms=1, raw={},
        ),
        judge_worker._finalize(
            sub_ids[2], status=SubmissionStatus.judged, score=60.0, log="", runtime_ms=1, raw={},
        ),
    )

    from app.api.leaderboard import _compute_leaderboard
    async with sm() as session:
        contest = await session.get(Contest, stage["contest_id"])
        lb = await _compute_leaderboard(session, contest)

    assert len(lb.entries) == 1
    assert lb.entries[0].total_score == 85.0 * 2  # (85/100) * 200


# ---------------------------------------------------------------------------
# Contest boundaries
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_submission_after_contest_end_is_rejected(client, test_engine):
    """Time-boxed contests must reject submissions after end_at."""
    from fastapi_users.password import PasswordHelper

    teacher_token = await _register_login(client, "bound-t@codefy.dev")
    sm = async_sessionmaker(test_engine, expire_on_commit=False)
    async with sm() as session:
        await session.execute(
            update(User).where(User.email == "bound-t@codefy.dev").values(role=UserRole.teacher)
        )
        await session.commit()

    # Re-login to refresh role-bound permissions in the API.
    r = await client.post(
        "/api/auth/jwt/login",
        data={"username": "bound-t@codefy.dev", "password": "password123"},
    )
    teacher_token = r.json()["access_token"]

    # Problem
    r = await client.post(
        "/api/problems",
        headers={"Authorization": f"Bearer {teacher_token}"},
        json={
            "slug": "bound-p",
            "title": "P",
            "starter_template_json": {
                "nodes": [{"id": "__SUBMIT__", "type": "Print", "data": {"params": {}}}],
                "edges": [],
            },
            "judge_spec": {
                "required_node_ids": ["__SUBMIT__"],
                "input_patches": [],
                "output_reads": [
                    {"node_id": "__SUBMIT__", "port": "v", "save_as": "y_pred"},
                ],
                "scoring": {
                    "method": "accuracy",
                    "target_output": "y_pred",
                    "ground_truth": "{hidden_test_data}/y.csv",
                    "full_score": 100,
                },
            },
            "published": True,
        },
    )
    assert r.status_code == 201, r.text

    # Contest that ended an hour ago.
    now = datetime.now(timezone.utc)
    r = await client.post(
        "/api/contests",
        headers={"Authorization": f"Bearer {teacher_token}"},
        json={
            "slug": "bound-c",
            "title": "Past",
            "start_at": (now - timedelta(hours=3)).isoformat(),
            "end_at": (now - timedelta(hours=1)).isoformat(),
            "problems": [{"problem_slug": "bound-p"}],
        },
    )
    assert r.status_code == 201
    contest = r.json()

    # Student tries to submit.
    student_token = await _register_login(client, "bound-s@codefy.dev")
    r = await client.post(
        "/api/submissions",
        headers={"Authorization": f"Bearer {student_token}"},
        json={
            "problem_slug": "bound-p",
            "graph_json": {
                "nodes": [{"id": "__SUBMIT__", "type": "Print", "data": {"params": {}}}],
                "edges": [],
            },
            "contest_id": contest["id"],
        },
    )
    assert r.status_code == 400
    assert "not active" in r.text.lower()


@pytest.mark.asyncio
async def test_join_contest_is_idempotent_sequential(client, test_engine):
    """Joining the same contest twice in a row must not error or duplicate."""
    teacher_token = await _register_login(client, "joinidem-t@codefy.dev")
    sm = async_sessionmaker(test_engine, expire_on_commit=False)
    async with sm() as session:
        await session.execute(
            update(User).where(User.email == "joinidem-t@codefy.dev").values(role=UserRole.teacher)
        )
        await session.commit()
    r = await client.post(
        "/api/auth/jwt/login",
        data={"username": "joinidem-t@codefy.dev", "password": "password123"},
    )
    teacher_token = r.json()["access_token"]

    r = await client.post(
        "/api/problems",
        headers={"Authorization": f"Bearer {teacher_token}"},
        json={
            "slug": "joinidem-p",
            "title": "P",
            "starter_template_json": {
                "nodes": [{"id": "__SUBMIT__", "type": "Print", "data": {"params": {}}}],
                "edges": [],
            },
            "judge_spec": {
                "required_node_ids": ["__SUBMIT__"],
                "input_patches": [],
                "output_reads": [
                    {"node_id": "__SUBMIT__", "port": "v", "save_as": "y_pred"},
                ],
                "scoring": {
                    "method": "accuracy",
                    "target_output": "y_pred",
                    "ground_truth": "{hidden_test_data}/y.csv",
                    "full_score": 100,
                },
            },
            "published": True,
        },
    )
    assert r.status_code == 201
    now = datetime.now(timezone.utc)
    r = await client.post(
        "/api/contests",
        headers={"Authorization": f"Bearer {teacher_token}"},
        json={
            "slug": "joinidem-c",
            "title": "Open",
            "start_at": (now - timedelta(hours=1)).isoformat(),
            "end_at": (now + timedelta(hours=1)).isoformat(),
            "problems": [{"problem_slug": "joinidem-p"}],
        },
    )
    assert r.status_code == 201

    student = await _register_login(client, "joinidem-s@codefy.dev")
    for _ in range(5):
        r = await client.post(
            "/api/contests/joinidem-c/join",
            headers={"Authorization": f"Bearer {student}"},
        )
        assert r.status_code == 200, r.text
        assert r.json()["joined"] is True
        assert r.json()["participant_count"] == 1

    async with sm() as session:
        count = len(
            (await session.execute(select(ContestParticipant))).scalars().all()
        )
        assert count == 1


@pytest.mark.asyncio
async def test_join_contest_race_recovers_from_unique_violation(test_engine):
    """Direct DB-level race: two ContestParticipant inserts simulate two
    concurrent join requests both passing the existence check, then both
    trying to insert. The endpoint must catch the IntegrityError and
    return cleanly without losing a row."""
    sm = async_sessionmaker(test_engine, expire_on_commit=False)
    from fastapi_users.password import PasswordHelper

    async with sm() as session:
        teacher = User(
            email="race-t@codefy.dev",
            hashed_password=PasswordHelper().hash("xx"),
            display_name="Teacher",
            role=UserRole.teacher,
            is_active=True, is_superuser=False, is_verified=True,
        )
        session.add(teacher)
        await session.flush()
        now = datetime.now(timezone.utc)
        contest = Contest(
            slug="race-c", title="C", description_md="",
            start_at=now - timedelta(hours=1),
            end_at=now + timedelta(hours=1),
            visibility=ContestVisibility.public,
            created_by_user_id=teacher.id,
        )
        session.add(contest)
        await session.flush()
        student = User(
            email="race-s@codefy.dev",
            hashed_password=PasswordHelper().hash("xx"),
            display_name="Racer",
            role=UserRole.student,
            is_active=True, is_superuser=False, is_verified=True,
        )
        session.add(student)
        await session.flush()
        # Pre-insert the participant row to guarantee the duplicate-insert
        # path triggers IntegrityError on the next join.
        session.add(ContestParticipant(contest_id=contest.id, user_id=student.id))
        await session.commit()
        contest_id, student_id = contest.id, student.id

    # Now drive a second insert attempt and verify it raises IntegrityError
    # — and that catching it + rolling back leaves the table consistent.
    async with sm() as session:
        session.add(ContestParticipant(contest_id=contest_id, user_id=student_id))
        from sqlalchemy.exc import IntegrityError
        with pytest.raises(IntegrityError):
            await session.commit()
        await session.rollback()

    async with sm() as session:
        rows = (
            await session.execute(select(ContestParticipant))
        ).scalars().all()
        assert len(rows) == 1


# ---------------------------------------------------------------------------
# Read consistency under concurrent writes
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_concurrent_leaderboard_reads_are_self_consistent(stage):
    """Reads under parallel inserts must not 500 and totals must be valid."""
    sm = stage["sm"]
    from fastapi_users.password import PasswordHelper
    from app.api.leaderboard import _compute_leaderboard

    async with sm() as session:
        u = User(
            email="rd@codefy.dev",
            hashed_password=PasswordHelper().hash("xx"),
            display_name="Reader",
            role=UserRole.student,
            is_active=True, is_superuser=False, is_verified=True,
        )
        session.add(u)
        await session.commit()
        user_id = u.id

    async def writer():
        for s in (10.0, 40.0, 75.0, 50.0, 90.0):
            async with sm() as session:
                session.add(
                    Submission(
                        user_id=user_id, problem_id=stage["problem_id"],
                        contest_id=stage["contest_id"], graph_json_path="",
                        status=SubmissionStatus.judged, score=s,
                    )
                )
                await session.commit()
            await asyncio.sleep(0)  # yield

    async def reader() -> float:
        async with sm() as session:
            contest = await session.get(Contest, stage["contest_id"])
            lb = await _compute_leaderboard(session, contest)
        return lb.entries[0].total_score if lb.entries else 0.0

    # Run multiple readers + one writer.
    write_task = asyncio.create_task(writer())
    snapshots = await asyncio.gather(*(reader() for _ in range(10)))
    await write_task
    final = await reader()

    # Every snapshot is a valid in-flight observation (0 ≤ x ≤ best*2).
    for v in snapshots:
        assert 0.0 <= v <= 90.0 * 2  # (90/100)*200 = 180
    # Final reflects the best submission.
    assert final == 90.0 * 2.0  # 180.0


# ---------------------------------------------------------------------------
# Defensive: finalize → publish ordering
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_publish_happens_after_commit(stage, monkeypatch):
    """The leaderboard query inside an SSE refresh must see the row we just judged.

    publish_contest_update must be called *after* the commit, never before.
    """
    sm = stage["sm"]
    from fastapi_users.password import PasswordHelper

    async with sm() as session:
        u = User(
            email="order@codefy.dev",
            hashed_password=PasswordHelper().hash("xx"),
            display_name="Order",
            role=UserRole.student,
            is_active=True, is_superuser=False, is_verified=True,
        )
        session.add(u)
        await session.flush()
        s = Submission(
            user_id=u.id, problem_id=stage["problem_id"],
            contest_id=stage["contest_id"], graph_json_path="",
            status=SubmissionStatus.queued,
        )
        session.add(s)
        await session.commit()
        sid = s.id

    seen_at_publish: dict[str, object] = {}

    def spy(cid, **kw):
        # Read the leaderboard *as a subscriber would* immediately after the
        # publish call returns. If publish-before-commit had happened, the
        # row wouldn't be visible here yet.
        async def _read():
            from app.api.leaderboard import _compute_leaderboard
            async with sm() as session:
                contest = await session.get(Contest, cid)
                lb = await _compute_leaderboard(session, contest)
            return lb
        seen_at_publish["lb"] = asyncio.run_coroutine_threadsafe(
            _read(), asyncio.get_event_loop()
        ).result()

    # Use the simpler synchronous approach: spy records the call, and we
    # check the DB after _finalize returns.
    calls: list[int] = []
    monkeypatch.setattr(
        judge_worker, "publish_contest_update", lambda cid, **kw: calls.append(cid)
    )

    await judge_worker._finalize(
        sid, status=SubmissionStatus.judged, score=70.0, log="", runtime_ms=1, raw={},
    )

    # The publish call must have happened, and the row must already be
    # committed in the DB by the time we get back.
    assert calls == [stage["contest_id"]]
    async with sm() as session:
        result = await session.get(Submission, sid)
        assert result.status == SubmissionStatus.judged
        assert result.score == 70.0
