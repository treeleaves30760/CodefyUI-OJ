"""SSE tests for /api/contests/{slug}/leaderboard/stream.

Two layers:

1. **HTTP-level auth** — uses the test client to verify status-code paths
   (401 missing token, 401 bad token, 401 inactive user, 404 unknown contest).

2. **Direct generator tests** — drive the SSE generator with a fake
   ``Request`` + a queue-backed pub/sub stub so we can exercise the streaming
   behaviour deterministically without the ASGI transport blocking forever.

The HTTP layer is too coarse to test stream content under ASGITransport —
the in-process transport buffers responses in ways that make iterating an
endless SSE generator slow to drain. Calling the generator function directly
keeps the tests focused on the behaviour we actually care about:

- The initial snapshot is the first event yielded.
- A new pub/sub message yields a fresh snapshot.
- A dead pub/sub source ends the generator (no infinite spin).
- Disconnect ends the generator promptly.
"""
from __future__ import annotations

import asyncio
import json
import os
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from datetime import datetime, timedelta, timezone

os.environ.setdefault("OJ_JUDGE_DISABLED", "true")
os.environ.setdefault("OJ_EVENTS_DISABLED", "true")
os.environ.setdefault("OJ_SSE_KEEPALIVE_SECONDS", "0.2")
os.environ.setdefault("OJ_SSE_DISCONNECT_POLL_SECONDS", "0.05")

import pytest
import pytest_asyncio
from httpx import AsyncClient
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import async_sessionmaker

from app.api import leaderboard as leaderboard_api
from app.models import Problem, Submission, SubmissionStatus, User
from app.models.contest import (
    Contest,
    ContestProblem,
    ContestVisibility,
)
from app.models.problem import ProblemDifficulty
from app.models.user import UserRole


# ---------------------------------------------------------------------------
# Fixtures + helpers
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


async def _make_setup(session, *, teacher_email: str, contest_slug: str, points: int = 100):
    from fastapi_users.password import PasswordHelper

    teacher = User(
        email=teacher_email,
        hashed_password=PasswordHelper().hash("doesntmatter"),
        display_name="Teacher",
        role=UserRole.teacher,
        is_active=True,
        is_superuser=False,
        is_verified=True,
    )
    session.add(teacher)
    await session.flush()
    problem = Problem(
        slug=f"{contest_slug}-p",
        title="P",
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
        slug=contest_slug,
        title=contest_slug,
        description_md="",
        start_at=now - timedelta(hours=1),
        end_at=now + timedelta(hours=2),
        visibility=ContestVisibility.public,
        created_by_user_id=teacher.id,
    )
    session.add(contest)
    await session.flush()
    session.add(
        ContestProblem(contest_id=contest.id, problem_id=problem.id, points=points)
    )
    await session.commit()
    return teacher.id, problem.id, contest.id


class _ManualStream:
    """Queue-backed async iterator we can drive from the test."""

    def __init__(self) -> None:
        self.queue: asyncio.Queue = asyncio.Queue()

    def push(self, msg: dict) -> None:
        self.queue.put_nowait(msg)

    def close(self) -> None:
        self.queue.put_nowait(None)

    def __aiter__(self) -> "_ManualStream":
        return self

    async def __anext__(self) -> dict:
        msg = await self.queue.get()
        if msg is None:
            raise StopAsyncIteration
        return msg


class _FakeRequest:
    """Just enough Request surface for the SSE generator to run.

    ``disconnect()`` flips the flag the generator polls via
    ``is_disconnected()`` so we can shut the stream down from the test.
    """

    def __init__(self) -> None:
        self._disconnected = False
        self.headers: dict[str, str] = {}

    def disconnect(self) -> None:
        self._disconnected = True

    async def is_disconnected(self) -> bool:
        return self._disconnected


def _parse_sse(buf: bytes) -> list[tuple[str, dict | str]]:
    """Return parsed (event, data) pairs; drops keepalive comments."""
    out: list[tuple[str, dict | str]] = []
    for block in buf.decode("utf-8", errors="replace").split("\n\n"):
        event = None
        data_lines: list[str] = []
        for line in block.splitlines():
            if line.startswith(":"):
                continue
            if line.startswith("event: "):
                event = line[len("event: "):].strip()
            elif line.startswith("data: "):
                data_lines.append(line[len("data: "):])
        if event and data_lines:
            raw = "\n".join(data_lines)
            try:
                out.append((event, json.loads(raw)))
            except json.JSONDecodeError:
                out.append((event, raw))
    return out


@pytest_asyncio.fixture(autouse=True)
async def _patch_session_maker(test_engine, monkeypatch):
    """Make the SSE generator's fresh-session calls hit the test engine."""
    sm = async_sessionmaker(test_engine, expire_on_commit=False)
    monkeypatch.setattr("app.db.async_session_maker", sm)


@pytest_asyncio.fixture
async def manual_subscribe(monkeypatch):
    stream = _ManualStream()

    @asynccontextmanager
    async def fake_subscribe(_contest_id: int):
        yield stream

    monkeypatch.setattr(leaderboard_api, "subscribe_contest_updates", fake_subscribe)
    return stream


async def _drive_generator(
    *, slug: str, request: _FakeRequest, manual_subscribe: _ManualStream
) -> AsyncIterator[bytes]:
    """Call the FastAPI handler directly and yield its raw SSE bytes."""
    sm = async_sessionmaker(_ENGINE_HOLDER["engine"], expire_on_commit=False)
    async with sm() as db:
        # Tell the handler the user is authenticated by short-circuiting auth.
        async def _fake_auth(_req, _tok, _db):
            return _AuthUser()

        # The handler is an async function that returns a StreamingResponse.
        # We monkey-patch _user_from_query_token to return a fake user so the
        # 401 branch is skipped, then call the handler with the test session.
        original = leaderboard_api._user_from_query_token
        leaderboard_api._user_from_query_token = _fake_auth
        try:
            resp = await leaderboard_api.contest_leaderboard_stream(
                slug=slug,
                request=request,  # type: ignore[arg-type]
                token=None,
                db=db,
            )
        finally:
            leaderboard_api._user_from_query_token = original

    body_iter = resp.body_iterator
    async for chunk in body_iter:
        yield chunk


class _AuthUser:
    is_active = True
    is_superuser = False


# Stash the test engine so _drive_generator can spin a fresh session.
_ENGINE_HOLDER: dict[str, object] = {}


@pytest_asyncio.fixture(autouse=True)
async def _hold_engine(test_engine):
    _ENGINE_HOLDER["engine"] = test_engine
    yield
    _ENGINE_HOLDER.pop("engine", None)


# ---------------------------------------------------------------------------
# HTTP auth tests — these only check status codes, no streaming consumption.
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_stream_without_token_returns_401(client, test_engine):
    sm = async_sessionmaker(test_engine, expire_on_commit=False)
    async with sm() as session:
        await _make_setup(session, teacher_email="sse-401@codefy.dev", contest_slug="sse-401")

    r = await client.get("/api/contests/sse-401/leaderboard/stream")
    assert r.status_code == 401


@pytest.mark.asyncio
async def test_stream_with_invalid_token_returns_401(client, test_engine):
    sm = async_sessionmaker(test_engine, expire_on_commit=False)
    async with sm() as session:
        await _make_setup(session, teacher_email="sse-bad@codefy.dev", contest_slug="sse-bad")

    r = await client.get("/api/contests/sse-bad/leaderboard/stream?token=garbage")
    assert r.status_code == 401


@pytest.mark.asyncio
async def test_stream_with_inactive_user_returns_401(client, test_engine):
    student_token = await _register_login(client, "sse-inactive@codefy.dev")
    sm = async_sessionmaker(test_engine, expire_on_commit=False)
    async with sm() as session:
        await _make_setup(
            session, teacher_email="sse-inactive-t@codefy.dev", contest_slug="sse-inactive-c"
        )
        await session.execute(
            update(User).where(User.email == "sse-inactive@codefy.dev").values(is_active=False)
        )
        await session.commit()

    r = await client.get(
        f"/api/contests/sse-inactive-c/leaderboard/stream?token={student_token}"
    )
    assert r.status_code == 401


@pytest.mark.asyncio
async def test_stream_404_for_unknown_contest(client):
    token = await _register_login(client, "sse-404@codefy.dev")
    r = await client.get(f"/api/contests/no-such-contest/leaderboard/stream?token={token}")
    assert r.status_code == 404


# ---------------------------------------------------------------------------
# Direct generator tests — full streaming behaviour, deterministic
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_generator_emits_initial_snapshot(test_engine, manual_subscribe):
    sm = async_sessionmaker(test_engine, expire_on_commit=False)
    async with sm() as session:
        _teacher_id, problem_id, contest_id = await _make_setup(
            session, teacher_email="g-init-t@codefy.dev", contest_slug="g-init"
        )
        # Pre-existing judged submission so the snapshot has a row.
        session.add(
            User(
                email="g-init-u@codefy.dev",
                hashed_password="x",
                display_name="u",
                role=UserRole.student,
                is_active=True, is_superuser=False, is_verified=True,
            )
        )
        await session.flush()
        u = (
            await session.execute(select(User).where(User.email == "g-init-u@codefy.dev"))
        ).scalar_one()
        session.add(
            Submission(
                user_id=u.id, problem_id=problem_id, contest_id=contest_id,
                graph_json_path="", status=SubmissionStatus.judged, score=33.0,
            )
        )
        await session.commit()

    request = _FakeRequest()
    gen = _drive_generator(slug="g-init", request=request, manual_subscribe=manual_subscribe)

    buf = bytearray()
    async def drain_until_event():
        async for chunk in gen:
            buf.extend(chunk)
            if _parse_sse(bytes(buf)):
                request.disconnect()
                manual_subscribe.close()
                break
    await asyncio.wait_for(drain_until_event(), timeout=5.0)

    events = _parse_sse(bytes(buf))
    assert events
    name, payload = events[0]
    assert name == "leaderboard"
    assert payload["contest_slug"] == "g-init"
    assert payload["entries"][0]["total_score"] == 33.0


@pytest.mark.asyncio
async def test_generator_pushes_after_publish(test_engine, manual_subscribe):
    sm = async_sessionmaker(test_engine, expire_on_commit=False)
    async with sm() as session:
        _teacher_id, problem_id, contest_id = await _make_setup(
            session, teacher_email="g-push-t@codefy.dev", contest_slug="g-push"
        )

    request = _FakeRequest()
    gen = _drive_generator(slug="g-push", request=request, manual_subscribe=manual_subscribe)

    buf = bytearray()

    async def drain_until_n(target: int):
        async for chunk in gen:
            buf.extend(chunk)
            if len(_parse_sse(bytes(buf))) >= target:
                return

    # Initial snapshot.
    await asyncio.wait_for(drain_until_n(1), timeout=5.0)
    first = _parse_sse(bytes(buf))
    assert first[0][1]["entries"] == []

    # Insert a judged submission and publish.
    async with sm() as session:
        session.add(
            User(
                email="g-push-u@codefy.dev",
                hashed_password="x",
                display_name="u2",
                role=UserRole.student,
                is_active=True, is_superuser=False, is_verified=True,
            )
        )
        await session.flush()
        u = (
            await session.execute(select(User).where(User.email == "g-push-u@codefy.dev"))
        ).scalar_one()
        session.add(
            Submission(
                user_id=u.id, problem_id=problem_id, contest_id=contest_id,
                graph_json_path="", status=SubmissionStatus.judged, score=88.0,
            )
        )
        await session.commit()
    manual_subscribe.push({"contest_id": contest_id, "reason": "submission"})

    try:
        await asyncio.wait_for(drain_until_n(2), timeout=5.0)
    finally:
        request.disconnect()
        manual_subscribe.close()

    events = _parse_sse(bytes(buf))
    assert len(events) >= 2
    assert events[-1][1]["entries"][0]["total_score"] == 88.0


@pytest.mark.asyncio
async def test_generator_exits_when_pubsub_source_dies(test_engine, monkeypatch):
    sm = async_sessionmaker(test_engine, expire_on_commit=False)
    async with sm() as session:
        await _make_setup(
            session, teacher_email="g-dead-t@codefy.dev", contest_slug="g-dead"
        )

    class _Broken:
        def __aiter__(self):
            return self

        async def __anext__(self):
            raise ConnectionError("redis gone")

    @asynccontextmanager
    async def broken(_cid):
        yield _Broken()

    monkeypatch.setattr(leaderboard_api, "subscribe_contest_updates", broken)

    request = _FakeRequest()
    gen = _drive_generator(slug="g-dead", request=request, manual_subscribe=_ManualStream())

    # Should drain to completion (StopAsyncIteration) without hanging.
    async def consume():
        async for _ in gen:
            pass
    await asyncio.wait_for(consume(), timeout=5.0)


@pytest.mark.asyncio
async def test_generator_exits_on_disconnect(test_engine, manual_subscribe):
    sm = async_sessionmaker(test_engine, expire_on_commit=False)
    async with sm() as session:
        await _make_setup(
            session, teacher_email="g-disc-t@codefy.dev", contest_slug="g-disc"
        )

    request = _FakeRequest()
    gen = _drive_generator(slug="g-disc", request=request, manual_subscribe=manual_subscribe)

    # Disconnect almost immediately.
    async def disconnector():
        await asyncio.sleep(0.3)
        request.disconnect()

    async def consume():
        async for _ in gen:
            pass

    await asyncio.gather(
        asyncio.wait_for(consume(), timeout=5.0),
        disconnector(),
    )
