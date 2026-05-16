"""Tests for the worker→SSE pub/sub bridge.

Goals:

- Publishing must never raise — the judge run should never fail because
  Redis is unreachable.
- Subscribe must gracefully fall back to a never-yielding stream when
  Redis is unavailable, so the SSE keepalive loop keeps the connection up.
- ``OJ_EVENTS_DISABLED=true`` short-circuits both sides — used by tests
  that don't want any Redis behaviour at all.
- The worker's ``_finalize`` publishes only when the submission has a
  ``contest_id``; non-contest submissions must not trigger a publish.
- Real-Redis roundtrip is skipped if redis isn't reachable, so the suite
  stays green on a developer laptop without docker.
"""
from __future__ import annotations

import asyncio
import json
import os
import socket

os.environ.setdefault("OJ_JUDGE_DISABLED", "true")

import pytest
import pytest_asyncio
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker

from app.judge.events import (
    _channel,
    _noop_stream,
    publish_contest_update,
    subscribe_contest_updates,
)
from app.models import Submission, SubmissionStatus
from app.models.contest import Contest, ContestVisibility
from app.models.problem import Problem, ProblemDifficulty
from app.models.user import User, UserRole


# ---------------------------------------------------------------------------
# Helpers / fixtures
# ---------------------------------------------------------------------------


def _redis_available() -> bool:
    """Probe via the same async client path subscribe_contest_updates uses.

    A bare TCP open can succeed against the wrong service, and the sync
    client succeeds in cases where the async pubsub path then times out.
    Be honest about what subscribe actually needs.
    """
    url = os.environ.get("REDIS_URL", "redis://localhost:6379/0")

    async def _probe() -> bool:
        try:
            from redis.asyncio import Redis  # type: ignore[import-not-found]

            conn = Redis.from_url(url, socket_connect_timeout=1, socket_timeout=1)
            try:
                pong = await asyncio.wait_for(conn.ping(), timeout=1.0)
                return bool(pong)
            finally:
                try:
                    await conn.aclose()
                except Exception:  # noqa: BLE001
                    pass
        except Exception:  # noqa: BLE001
            return False

    try:
        return asyncio.run(_probe())
    except Exception:  # noqa: BLE001
        return False


needs_redis = pytest.mark.skipif(
    not _redis_available(), reason="Redis is not reachable on REDIS_URL"
)


@pytest_asyncio.fixture
async def seeded_session(test_engine, monkeypatch):
    from app.db import Base  # noqa: F401 — ensures metadata is loaded

    sm = async_sessionmaker(test_engine, expire_on_commit=False)
    monkeypatch.setattr("app.db.async_session_maker", sm)
    monkeypatch.setattr("app.judge.worker.async_session_maker", sm)
    yield sm


# ---------------------------------------------------------------------------
# Channel name stability
# ---------------------------------------------------------------------------


def test_channel_naming_is_stable():
    assert _channel(7) == "oj:contest:7:updates"
    assert _channel(123) == "oj:contest:123:updates"


# ---------------------------------------------------------------------------
# Defensive publish behaviour
# ---------------------------------------------------------------------------


def test_publish_with_events_disabled_is_noop(monkeypatch):
    """OJ_EVENTS_DISABLED=true should short-circuit before touching redis."""
    calls = []

    monkeypatch.setenv("OJ_EVENTS_DISABLED", "true")

    def boom(*_a, **_k):
        calls.append("redis-touched")
        raise AssertionError("publish should not have hit redis")

    monkeypatch.setattr("redis.Redis.from_url", boom)
    publish_contest_update(1)
    assert calls == []


def test_publish_swallows_redis_errors(monkeypatch):
    """If redis is unreachable, publish must not raise."""
    monkeypatch.delenv("OJ_EVENTS_DISABLED", raising=False)

    class BrokenRedis:
        @classmethod
        def from_url(cls, *_a, **_k):
            raise ConnectionError("nope")

    monkeypatch.setattr("redis.Redis.from_url", BrokenRedis.from_url)
    # Must not raise.
    publish_contest_update(42, reason="test")


def test_publish_closes_connection_even_on_error(monkeypatch):
    monkeypatch.delenv("OJ_EVENTS_DISABLED", raising=False)
    closed = {"flag": False}

    class FakeRedis:
        def __init__(self):
            self.published = False

        @classmethod
        def from_url(cls, *_a, **_k):
            return cls()

        def publish(self, *_a, **_k):
            raise RuntimeError("publish failed mid-call")

        def close(self):
            closed["flag"] = True

    monkeypatch.setattr("redis.Redis.from_url", FakeRedis.from_url)
    publish_contest_update(1)
    assert closed["flag"] is True


# ---------------------------------------------------------------------------
# Defensive subscribe behaviour
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_subscribe_with_events_disabled_returns_noop_stream(monkeypatch):
    monkeypatch.setenv("OJ_EVENTS_DISABLED", "true")
    async with subscribe_contest_updates(99) as stream:
        # noop stream never yields within a reasonable wait
        with pytest.raises(asyncio.TimeoutError):
            await asyncio.wait_for(stream.__anext__(), timeout=0.2)


@pytest.mark.asyncio
async def test_subscribe_with_unreachable_redis_returns_noop_stream(monkeypatch):
    monkeypatch.delenv("OJ_EVENTS_DISABLED", raising=False)

    class BoomAsyncRedis:
        @classmethod
        def from_url(cls, *_a, **_k):
            raise ConnectionError("redis down")

    monkeypatch.setattr("redis.asyncio.Redis.from_url", BoomAsyncRedis.from_url)
    async with subscribe_contest_updates(1) as stream:
        with pytest.raises(asyncio.TimeoutError):
            await asyncio.wait_for(stream.__anext__(), timeout=0.2)


@pytest.mark.asyncio
async def test_noop_stream_is_an_async_iterator():
    gen = _noop_stream()
    # confirm it has the protocol; the close call returns a coroutine on
    # 3.13+, so await it to avoid a ResourceWarning.
    assert hasattr(gen, "__anext__")
    closer = gen.aclose()
    if asyncio.iscoroutine(closer):
        await closer


# ---------------------------------------------------------------------------
# Worker → publish hook
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_finalize_publishes_when_contest_id_set(seeded_session, monkeypatch):
    from app.judge import worker
    from fastapi_users.password import PasswordHelper

    sm = seeded_session
    calls = []

    monkeypatch.setattr(
        worker, "publish_contest_update", lambda cid, **kw: calls.append((cid, kw))
    )

    async with sm() as session:
        # Set up the dependency rows we need.
        user = User(
            email="finaliser@codefy.dev",
            hashed_password=PasswordHelper().hash("xxx"),
            display_name="f",
            role=UserRole.student,
            is_active=True,
            is_superuser=False,
            is_verified=True,
        )
        session.add(user)
        await session.flush()

        problem = Problem(
            slug="finalize-p",
            title="x",
            statement_md="",
            difficulty=ProblemDifficulty.easy,
            tags=[],
            starter_template_json={"nodes": [], "edges": []},
            judge_spec={"scoring": {"full_score": 100}},
            time_limit_seconds=30,
            memory_limit_mb=512,
            published=True,
            created_by_user_id=user.id,
        )
        session.add(problem)
        await session.flush()

        from datetime import datetime, timedelta, timezone

        now = datetime.now(timezone.utc)
        contest = Contest(
            slug="finalize-c",
            title="x",
            description_md="",
            start_at=now - timedelta(hours=1),
            end_at=now + timedelta(hours=1),
            visibility=ContestVisibility.public,
            created_by_user_id=user.id,
        )
        session.add(contest)
        await session.flush()

        sub = Submission(
            user_id=user.id,
            problem_id=problem.id,
            contest_id=contest.id,
            graph_json_path="",
            status=SubmissionStatus.judging,
        )
        session.add(sub)
        await session.commit()
        sub_id = sub.id
        cid = contest.id

    await worker._finalize(
        sub_id,
        status=SubmissionStatus.judged,
        score=42.0,
        log="ok",
        runtime_ms=100,
        raw={"score": 42.0, "status": "judged"},
    )

    assert calls == [(cid, {"reason": "submission"})]


@pytest.mark.asyncio
async def test_finalize_does_not_publish_when_no_contest(seeded_session, monkeypatch):
    from app.judge import worker
    from fastapi_users.password import PasswordHelper

    sm = seeded_session
    calls = []
    monkeypatch.setattr(
        worker, "publish_contest_update", lambda cid, **kw: calls.append((cid, kw))
    )

    async with sm() as session:
        user = User(
            email="practiser@codefy.dev",
            hashed_password=PasswordHelper().hash("xxx"),
            display_name="p",
            role=UserRole.student,
            is_active=True,
            is_superuser=False,
            is_verified=True,
        )
        session.add(user)
        await session.flush()
        problem = Problem(
            slug="np-1",
            title="x",
            statement_md="",
            difficulty=ProblemDifficulty.easy,
            tags=[],
            starter_template_json={"nodes": [], "edges": []},
            judge_spec={"scoring": {"full_score": 100}},
            time_limit_seconds=30,
            memory_limit_mb=512,
            published=True,
            created_by_user_id=user.id,
        )
        session.add(problem)
        await session.flush()
        sub = Submission(
            user_id=user.id,
            problem_id=problem.id,
            contest_id=None,  # the key bit
            graph_json_path="",
            status=SubmissionStatus.judging,
        )
        session.add(sub)
        await session.commit()
        sub_id = sub.id

    await worker._finalize(
        sub_id,
        status=SubmissionStatus.judged,
        score=42.0,
        log="ok",
        runtime_ms=100,
        raw={},
    )

    assert calls == []


@pytest.mark.asyncio
async def test_finalize_handles_missing_submission(seeded_session, monkeypatch):
    """If the submission row vanishes mid-flight, _finalize must return cleanly."""
    from app.judge import worker

    calls = []
    monkeypatch.setattr(
        worker, "publish_contest_update", lambda cid, **kw: calls.append((cid, kw))
    )

    # ID that doesn't exist
    await worker._finalize(
        999_999,
        status=SubmissionStatus.judged,
        score=10.0,
        log="x",
        runtime_ms=1,
        raw=None,
    )
    assert calls == []


# ---------------------------------------------------------------------------
# Real-Redis roundtrip (optional)
# ---------------------------------------------------------------------------


@needs_redis
@pytest.mark.asyncio
async def test_publish_subscribe_roundtrip(monkeypatch):
    """When Redis is up, a publish must reach a live subscriber."""
    monkeypatch.delenv("OJ_EVENTS_DISABLED", raising=False)

    received: list[dict] = []
    ready = asyncio.Event()

    async def subscriber():
        async with subscribe_contest_updates(31415) as stream:
            ready.set()
            received.append(await asyncio.wait_for(stream.__anext__(), timeout=3.0))

    task = asyncio.create_task(subscriber())
    await ready.wait()
    # Tiny pause for the subscription to be active on the redis side
    await asyncio.sleep(0.05)
    publish_contest_update(31415, reason="roundtrip")
    await asyncio.wait_for(task, timeout=3.0)

    assert received == [{"contest_id": 31415, "reason": "roundtrip"}]
