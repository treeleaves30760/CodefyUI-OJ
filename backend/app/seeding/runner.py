"""Idempotent seed for the OJ.

Run via ``python -m app.seeding.runner`` after alembic migrations. Re-running
is safe — every step checks for an existing record first and skips on hit.

Seeding does **not** create the admin user. The first admin is created via the
``/setup`` UI on first boot, or via ``BOOTSTRAP_ADMIN_*`` env vars handled in
``app.main:lifespan``. If no admin exists when the seeder runs, problem seeding
is skipped with a warning — re-run after setup to get the baseline problems.

What gets seeded (when an owner is available):
1. Five baseline problems with starter templates, judge specs, and hidden
   test data written into ``storage/test_data/<slug>/``.
2. A default contest that includes all seeded problems, open from "now" for
   30 days, public visibility, with per-problem ``points`` from the seed.
   In ``APP_MODE=practice``, the contest is skipped (no contest concept).

Environment knobs:
    OJ_SEED_ENABLED       set to "false" to skip everything (default: "true").
    OJ_SEED_CONTEST_SLUG  default: "starter-cup"
"""
from __future__ import annotations

import asyncio
import logging
import os
from datetime import datetime, timedelta, timezone
from pathlib import Path

from sqlalchemy import or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import PRACTICE_USER_EMAIL, get_settings
from app.core.storage import ensure_dir, get_test_data_dir
from app.db import async_session_maker
from app.models import Problem, User, UserRole
from app.models.contest import (
    Contest,
    ContestProblem,
    ContestVisibility,
)
from app.seeding.problems import SEED_PROBLEMS, SeedProblem

logger = logging.getLogger("oj.seed")


def _env(name: str, default: str) -> str:
    value = os.environ.get(name, "")
    return value if value else default


async def _find_seed_owner(session: AsyncSession) -> User | None:
    """Return the user who should own seeded problems/contests, or None.

    In competition mode we look for any admin/superuser. In practice mode we
    use the shared practice user. If neither is available yet (e.g. first boot
    with no setup performed), seeding is deferred — caller will skip.
    """
    settings = get_settings()
    if settings.app_mode == "practice":
        result = await session.execute(
            select(User).where(User.email == PRACTICE_USER_EMAIL)
        )
        return result.scalar_one_or_none()

    result = await session.execute(
        select(User)
        .where(or_(User.role == UserRole.admin, User.is_superuser.is_(True)))
        .order_by(User.id)
        .limit(1)
    )
    return result.scalar_one_or_none()


def _write_test_data(slug: str, train_csv: str, test_features_csv: str, test_labels_csv: str) -> Path:
    test_dir = ensure_dir(get_test_data_dir(slug))
    (test_dir / "train.csv").write_text(train_csv, encoding="utf-8")
    (test_dir / "test_features.csv").write_text(test_features_csv, encoding="utf-8")
    (test_dir / "test_labels.csv").write_text(test_labels_csv, encoding="utf-8")
    return test_dir


async def _ensure_problem(
    session: AsyncSession, sp: SeedProblem, author_id: int, practice_visible: bool
) -> Problem:
    existing = (
        await session.execute(select(Problem).where(Problem.slug == sp.slug))
    ).scalar_one_or_none()

    train_csv, test_features_csv, test_labels_csv = sp.dataset()
    test_dir = _write_test_data(sp.slug, train_csv, test_features_csv, test_labels_csv)
    test_path = str(test_dir.resolve())

    if existing:
        # Keep test data fresh in case the dataset generator changes between
        # deploys. We deliberately don't overwrite mutable fields like title /
        # statement / judge_spec — a teacher may have edited them in the UI.
        existing.hidden_test_data_path = test_path
        if practice_visible and not existing.practice_visible:
            existing.practice_visible = True
        await session.commit()
        return existing

    problem = Problem(
        slug=sp.slug,
        title=sp.title,
        statement_md=sp.statement_md,
        difficulty=sp.difficulty,
        tags=list(sp.tags),
        starter_template_json=sp.starter_template,
        judge_spec=sp.judge_spec,
        hidden_test_data_path=test_path,
        time_limit_seconds=sp.time_limit_seconds,
        memory_limit_mb=sp.memory_limit_mb,
        published=True,
        practice_visible=practice_visible,
        created_by_user_id=author_id,
    )
    session.add(problem)
    try:
        await session.commit()
    except IntegrityError:
        await session.rollback()
        existing = (
            await session.execute(select(Problem).where(Problem.slug == sp.slug))
        ).scalar_one()
        existing.hidden_test_data_path = test_path
        await session.commit()
        logger.info("seed: problem %s already inserted by concurrent run", sp.slug)
        return existing
    await session.refresh(problem)
    logger.info("seed: created problem %s", sp.slug)
    return problem


async def _ensure_starter_contest(
    session: AsyncSession,
    owner: User,
    problems: dict[str, Problem],
) -> Contest:
    slug = _env("OJ_SEED_CONTEST_SLUG", "starter-cup")
    contest = (
        await session.execute(select(Contest).where(Contest.slug == slug))
    ).scalar_one_or_none()
    now = datetime.now(timezone.utc)

    if contest is None:
        contest = Contest(
            slug=slug,
            title="OJ 起跑賽 / Starter Cup",
            description_md=(
                f"歡迎來到 CodefyUI 線上評測系統！這場常駐競賽包含 {len(SEED_PROBLEMS)} "
                "個入門題目，從資料流暖身、分類到迴歸都涵蓋了。加入比賽後就能上傳 "
                "`graph.json` 進行評測，排行榜會即時更新。\n\n"
                f"Welcome to the CodefyUI Online Judge. This always-on contest "
                f"covers a {len(SEED_PROBLEMS)}-problem warmup set — pipeline IO, "
                "classification, and regression. Join the contest, upload your "
                "`graph.json`, and watch the leaderboard update in real time.\n"
            ),
            start_at=now - timedelta(minutes=5),
            end_at=now + timedelta(days=365),
            visibility=ContestVisibility.public,
            created_by_user_id=owner.id,
        )
        session.add(contest)
        try:
            await session.flush()
        except IntegrityError:
            await session.rollback()
            contest = (
                await session.execute(select(Contest).where(Contest.slug == slug))
            ).scalar_one()
            logger.info("seed: contest %s already inserted by concurrent run", slug)
        else:
            logger.info("seed: created contest %s", slug)

    existing_links_result = await session.execute(
        select(ContestProblem.problem_id).where(ContestProblem.contest_id == contest.id)
    )
    existing_problem_ids = {row[0] for row in existing_links_result}

    for order, sp in enumerate(SEED_PROBLEMS):
        problem = problems.get(sp.slug)
        if problem is None or problem.id in existing_problem_ids:
            continue
        session.add(
            ContestProblem(
                contest_id=contest.id,
                problem_id=problem.id,
                points=sp.points,
                display_order=order,
            )
        )

    try:
        await session.commit()
    except IntegrityError:
        # Another seed inserted the same contest_problem rows concurrently;
        # the unique (contest_id, problem_id) constraint kicked in. Drop and
        # re-fetch — the rows are now there either way.
        await session.rollback()
    await session.refresh(contest)
    return contest


async def seed() -> None:
    settings = get_settings()
    settings.storage_root.mkdir(parents=True, exist_ok=True)
    settings.test_data_dir.mkdir(parents=True, exist_ok=True)

    async with async_session_maker() as session:
        owner = await _find_seed_owner(session)
        if owner is None:
            logger.warning(
                "seed: no owner available (no admin in competition mode, or no "
                "practice user in practice mode). Skipping problem/contest seed. "
                "Run setup UI / bootstrap an admin and re-run the seeder."
            )
            return

        is_practice = settings.app_mode == "practice"

        problems: dict[str, Problem] = {}
        for sp in SEED_PROBLEMS:
            problems[sp.slug] = await _ensure_problem(
                session, sp, owner.id, practice_visible=is_practice
            )

        # Contest only makes sense in competition mode — practice has no
        # contest UI and no notion of "joining" anything.
        if not is_practice:
            await _ensure_starter_contest(session, owner, problems)


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s %(message)s")
    if _env("OJ_SEED_ENABLED", "true").lower() not in ("1", "true", "yes", "on"):
        logger.info("seed: OJ_SEED_ENABLED=false — skipping")
        return
    asyncio.run(seed())


if __name__ == "__main__":
    main()
