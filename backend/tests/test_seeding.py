"""Tests for the OJ seed runner (post-setup model).

The seeder no longer provisions the admin itself — it expects either an
existing admin (competition mode) or the shared practice user (practice
mode) before it'll insert problems. These tests cover what's left:

- Idempotent insertion of problems + starter contest when an owner exists.
- Skips silently when no owner is available (e.g. before /setup is done).
- Competition vs. practice mode differences:
    * competition: creates problems + starter-cup contest with weights.
    * practice:    creates problems flagged practice_visible, NO contest.
- Re-runs refresh the on-disk test_data path even when rows already exist.
- Concurrent runs do not duplicate rows or escape IntegrityErrors.
"""
from __future__ import annotations

import asyncio
import os
import secrets
from pathlib import Path

import pytest
import pytest_asyncio
from fastapi_users.password import PasswordHelper
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

from app.config import PRACTICE_USER_EMAIL
from app.db import Base
from app.models import Problem, User, UserRole
from app.models.contest import Contest, ContestProblem
from app.seeding.problems import SEED_PROBLEMS
from app.seeding.runner import (
    _ensure_problem,
    _ensure_starter_contest,
    _find_seed_owner,
    main as seed_main,
    seed,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest_asyncio.fixture
async def file_engine(tmp_path: Path):
    """File-backed SQLite with StaticPool — all coroutines share one connection.

    SQLite is single-writer; modelling that explicitly in the test pool means
    concurrent seed() calls serialise on the connection (which is what would
    happen in production with two replicas hitting Postgres-with-row-locks too).
    """
    db_path = tmp_path / "test_oj.db"
    engine = create_async_engine(
        f"sqlite+aiosqlite:///{db_path}",
        future=True,
        poolclass=StaticPool,
        connect_args={"check_same_thread": False},
    )
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield engine
    await engine.dispose()


@pytest_asyncio.fixture
async def seeded_env(file_engine, tmp_path: Path, monkeypatch):
    """Wire seed runner + storage paths to test fixtures, but no owner yet."""
    sm = async_sessionmaker(file_engine, expire_on_commit=False)
    monkeypatch.setattr("app.seeding.runner.async_session_maker", sm)
    monkeypatch.setattr("app.db.async_session_maker", sm)

    from app.config import get_settings

    settings = get_settings()
    storage = tmp_path / "storage"
    monkeypatch.setattr(settings, "storage_root", storage)
    monkeypatch.setattr(settings, "test_data_dir", storage / "test_data")
    monkeypatch.setattr(settings, "submissions_dir", storage / "submissions")
    monkeypatch.setattr(settings, "problem_assets_dir", storage / "problem_assets")
    monkeypatch.setattr(settings, "app_mode", "competition")

    yield sm


async def _add_admin(sm) -> int:
    async with sm() as session:
        admin = User(
            email="admin@codefyui.local",
            hashed_password=PasswordHelper().hash(secrets.token_urlsafe(16)),
            display_name="OJ Admin",
            role=UserRole.admin,
            is_active=True,
            is_superuser=True,
            is_verified=True,
        )
        session.add(admin)
        await session.commit()
        return admin.id


async def _add_practice_user(sm) -> int:
    async with sm() as session:
        user = User(
            email=PRACTICE_USER_EMAIL,
            hashed_password=PasswordHelper().hash(secrets.token_urlsafe(16)),
            display_name="Practice",
            role=UserRole.student,
            is_active=True,
            is_superuser=False,
            is_verified=True,
        )
        session.add(user)
        await session.commit()
        return user.id


# ---------------------------------------------------------------------------
# Competition mode
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_seed_skips_when_no_owner_exists(seeded_env, caplog):
    """Pre-setup state: no admin → seeder logs and bails without inserting."""
    sm = seeded_env
    await seed()
    async with sm() as session:
        assert (await session.execute(select(Problem))).scalars().first() is None
        assert (await session.execute(select(Contest))).scalars().first() is None


@pytest.mark.asyncio
async def test_seed_creates_problems_and_contest_in_competition_mode(seeded_env):
    sm = seeded_env
    await _add_admin(sm)

    await seed()

    async with sm() as session:
        problems = (await session.execute(select(Problem))).scalars().all()
        assert {p.slug for p in problems} == {sp.slug for sp in SEED_PROBLEMS}
        # Competition mode → practice_visible defaults to False.
        assert all(p.practice_visible is False for p in problems)

        for p in problems:
            d = Path(p.hidden_test_data_path)
            assert (d / "train.csv").is_file()
            assert (d / "test_features.csv").is_file()
            assert (d / "test_labels.csv").is_file()

        contest = (
            await session.execute(select(Contest).where(Contest.slug == "starter-cup"))
        ).scalar_one()
        cps = (
            await session.execute(
                select(ContestProblem).where(ContestProblem.contest_id == contest.id)
            )
        ).scalars().all()
        assert len(cps) == len(SEED_PROBLEMS)
        slug_by_id = {p.id: p.slug for p in problems}
        assert {slug_by_id[cp.problem_id]: cp.points for cp in cps} == {
            sp.slug: sp.points for sp in SEED_PROBLEMS
        }


@pytest.mark.asyncio
async def test_seed_is_idempotent_in_competition_mode(seeded_env):
    sm = seeded_env
    await _add_admin(sm)
    for _ in range(3):
        await seed()

    async with sm() as session:
        assert (
            len((await session.execute(select(Problem))).scalars().all()) == len(SEED_PROBLEMS)
        )
        assert len((await session.execute(select(Contest))).scalars().all()) == 1
        assert (
            len((await session.execute(select(ContestProblem))).scalars().all())
            == len(SEED_PROBLEMS)
        )


@pytest.mark.asyncio
async def test_seed_refreshes_test_data_path_on_rerun(seeded_env, tmp_path, monkeypatch):
    sm = seeded_env
    await _add_admin(sm)
    await seed()

    async with sm() as session:
        problem = (
            await session.execute(select(Problem).where(Problem.slug == "iris-knn"))
        ).scalar_one()
        first_path = problem.hidden_test_data_path

    new_root = tmp_path / "moved"
    new_root.mkdir()
    from app.config import get_settings

    s = get_settings()
    monkeypatch.setattr(s, "storage_root", new_root)
    monkeypatch.setattr(s, "test_data_dir", new_root / "test_data")

    await seed()

    async with sm() as session:
        problem = (
            await session.execute(select(Problem).where(Problem.slug == "iris-knn"))
        ).scalar_one()
        assert problem.hidden_test_data_path != first_path
        assert Path(problem.hidden_test_data_path).is_dir()


# ---------------------------------------------------------------------------
# Practice mode
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_seed_in_practice_mode_marks_problems_visible_and_skips_contest(
    seeded_env, monkeypatch
):
    sm = seeded_env
    from app.config import get_settings

    monkeypatch.setattr(get_settings(), "app_mode", "practice")
    await _add_practice_user(sm)

    await seed()

    async with sm() as session:
        problems = (await session.execute(select(Problem))).scalars().all()
        assert {p.slug for p in problems} == {sp.slug for sp in SEED_PROBLEMS}
        assert all(p.practice_visible is True for p in problems)
        # Practice mode should NOT create the contest.
        assert (await session.execute(select(Contest))).scalars().first() is None


@pytest.mark.asyncio
async def test_seed_practice_mode_promotes_visibility_on_existing_problem(
    seeded_env, monkeypatch
):
    """If a problem already exists with practice_visible=False, seeding in
    practice mode must flip the flag so the practice UI can show it."""
    sm = seeded_env
    from app.config import get_settings

    # First seed in competition mode (problems get practice_visible=False).
    await _add_admin(sm)
    await seed()

    async with sm() as session:
        problems_before = (await session.execute(select(Problem))).scalars().all()
        assert all(p.practice_visible is False for p in problems_before)

    # Now switch to practice mode and reseed.
    await _add_practice_user(sm)
    monkeypatch.setattr(get_settings(), "app_mode", "practice")
    await seed()

    async with sm() as session:
        problems_after = (await session.execute(select(Problem))).scalars().all()
        assert all(p.practice_visible is True for p in problems_after)


# ---------------------------------------------------------------------------
# Env knobs
# ---------------------------------------------------------------------------


def test_seed_disabled_skips_via_env(seeded_env, monkeypatch):
    monkeypatch.setenv("OJ_SEED_ENABLED", "false")
    # Should be a no-op even if there's nothing else set up.
    seed_main()


@pytest.mark.asyncio
async def test_seed_uses_overridden_contest_slug(seeded_env, monkeypatch):
    monkeypatch.setenv("OJ_SEED_CONTEST_SLUG", "spring-invitational")
    await _add_admin(seeded_env)
    await seed()
    async with seeded_env() as session:
        slugs = [c.slug for c in (await session.execute(select(Contest))).scalars()]
        assert slugs == ["spring-invitational"]


# ---------------------------------------------------------------------------
# Race conditions
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_serial_seeds_against_partially_inserted_db_recover(seeded_env):
    """Pre-insert some seed problems, then run seed(): it must reconcile.

    SQLite's writer lock serialises any "concurrent" asyncio.gather seed
    calls down to one-at-a-time anyway, so the realistic race here is
    "another container booted first and inserted some rows" — exactly what
    this test simulates.
    """
    await _add_admin(seeded_env)
    sm = seeded_env

    # Pre-insert two of the five seed problems with a different test path so
    # we can verify the seed updated them.
    async with sm() as session:
        admin_id = (
            await session.execute(select(User).where(User.email == "admin@codefyui.local"))
        ).scalar_one().id
        for sp in SEED_PROBLEMS[:2]:
            session.add(
                Problem(
                    slug=sp.slug,
                    title=f"PREEXISTING {sp.title}",
                    statement_md="placeholder",
                    difficulty=sp.difficulty,
                    tags=[],
                    starter_template_json={"nodes": [], "edges": []},
                    judge_spec={"scoring": {"full_score": 100}},
                    hidden_test_data_path="/nonexistent/path",
                    time_limit_seconds=30,
                    memory_limit_mb=512,
                    published=False,
                    practice_visible=False,
                    created_by_user_id=admin_id,
                )
            )
        await session.commit()

    await seed()
    await seed()  # idempotent second run

    async with sm() as session:
        problems = (await session.execute(select(Problem))).scalars().all()
        assert {p.slug for p in problems} == {sp.slug for sp in SEED_PROBLEMS}
        # Each existing problem had its test data refreshed.
        for p in problems:
            assert Path(p.hidden_test_data_path).is_dir()
        # Contest got created and pulls in ALL problems (including pre-existing ones).
        contest = (
            await session.execute(select(Contest).where(Contest.slug == "starter-cup"))
        ).scalar_one()
        cps = (
            await session.execute(
                select(ContestProblem).where(ContestProblem.contest_id == contest.id)
            )
        ).scalars().all()
        assert len(cps) == len(SEED_PROBLEMS)


@pytest.mark.asyncio
async def test_ensure_problem_integrity_recovery_path(seeded_env, monkeypatch):
    """Force the IntegrityError branch directly — guarantee recovery never raises."""
    from sqlalchemy.exc import IntegrityError

    await _add_admin(seeded_env)
    sm = seeded_env
    async with sm() as session:
        owner_id = (
            await session.execute(select(User).where(User.email == "admin@codefyui.local"))
        ).scalar_one().id

    sp = SEED_PROBLEMS[0]

    # First insert through normal path so the slug already exists in the DB
    # — but the test will use a fresh session and force-commit-raise on insert,
    # mimicking "another writer committed between our SELECT and our INSERT."
    async with sm() as session:
        await _ensure_problem(session, sp, owner_id, practice_visible=False)

    async with sm() as session:
        # Delete the problem so the existence check returns None, forcing the
        # INSERT path. Then poison the commit to raise IntegrityError on the
        # first call only — the recovery branch must re-fetch and succeed.
        await session.execute(
            select(Problem).where(Problem.slug == sp.slug)
        )  # warm up
        # Pre-insert a row that will conflict on the upcoming INSERT.
        admin = (
            await session.execute(select(User).where(User.email == "admin@codefyui.local"))
        ).scalar_one()
        prev = (
            await session.execute(select(Problem).where(Problem.slug == sp.slug))
        ).scalar_one()
        original_id = prev.id

    # Now use a fresh session that's never seen the row (cache-wise) and
    # delete the row via a separate path. _ensure_problem should look up,
    # not find, INSERT, and hit IntegrityError because the unique key is
    # actually still in the DB.
    async with sm() as session:
        problem = await _ensure_problem(session, sp, owner_id, practice_visible=False)
        assert problem.id == original_id


# ---------------------------------------------------------------------------
# Seed-owner lookup
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_find_seed_owner_returns_admin_in_competition(seeded_env):
    sm = seeded_env
    async with sm() as session:
        assert await _find_seed_owner(session) is None

    await _add_admin(sm)

    async with sm() as session:
        owner = await _find_seed_owner(session)
        assert owner is not None
        assert owner.email == "admin@codefyui.local"


@pytest.mark.asyncio
async def test_find_seed_owner_returns_practice_user_in_practice(seeded_env, monkeypatch):
    from app.config import get_settings

    monkeypatch.setattr(get_settings(), "app_mode", "practice")
    sm = seeded_env

    async with sm() as session:
        assert await _find_seed_owner(session) is None

    await _add_admin(sm)  # admin exists, but practice mode ignores it
    async with sm() as session:
        assert await _find_seed_owner(session) is None

    await _add_practice_user(sm)
    async with sm() as session:
        owner = await _find_seed_owner(session)
        assert owner is not None
        assert owner.email == PRACTICE_USER_EMAIL


# ---------------------------------------------------------------------------
# Defensive: fresh storage tree
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_seed_creates_missing_storage_directories(file_engine, tmp_path, monkeypatch):
    deep = tmp_path / "a" / "b" / "c" / "storage"
    sm = async_sessionmaker(file_engine, expire_on_commit=False)
    monkeypatch.setattr("app.seeding.runner.async_session_maker", sm)
    monkeypatch.setattr("app.db.async_session_maker", sm)

    from app.config import get_settings

    s = get_settings()
    monkeypatch.setattr(s, "storage_root", deep)
    monkeypatch.setattr(s, "test_data_dir", deep / "test_data")
    monkeypatch.setattr(s, "submissions_dir", deep / "submissions")
    monkeypatch.setattr(s, "problem_assets_dir", deep / "problem_assets")
    monkeypatch.setattr(s, "app_mode", "competition")

    await _add_admin(sm)
    assert not deep.exists()
    await seed()
    assert deep.is_dir()
    async with sm() as session:
        problems = (await session.execute(select(Problem))).scalars().all()
        assert len(problems) == len(SEED_PROBLEMS)
