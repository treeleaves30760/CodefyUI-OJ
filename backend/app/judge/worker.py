"""RQ worker entry — picks a submission, prepares workspace, runs the judge,
records result.

For dev/test the same function is called inline via OJ_JUDGE_INLINE=true.
"""
from __future__ import annotations

import asyncio
import json
import logging
import os
import socket
from datetime import datetime, timezone
from pathlib import Path

from sqlalchemy import select

from app.core.storage import ensure_dir, get_submission_dir
from app.db import async_session_maker
from app.judge.runner import run_judge
from app.models import Problem, Submission, SubmissionStatus

logger = logging.getLogger(__name__)


def judge_submission_sync(submission_id: int) -> None:
    """Synchronous entry compatible with RQ enqueue."""
    asyncio.run(_judge_submission_async(submission_id))


async def _judge_submission_async(submission_id: int) -> None:
    worker_id = f"{socket.gethostname()}/{os.getpid()}"
    started = datetime.now(timezone.utc)

    async with async_session_maker() as session:
        sub = await session.get(Submission, submission_id)
        if sub is None:
            logger.warning("submission %s not found", submission_id)
            return
        problem = await session.get(Problem, sub.problem_id)
        if problem is None:
            sub.status = SubmissionStatus.error
            sub.judge_log = "Problem record missing"
            sub.judge_finished_at = datetime.now(timezone.utc)
            await session.commit()
            return

        sub.status = SubmissionStatus.judging
        sub.worker_id = worker_id
        sub.judge_started_at = started
        await session.commit()

        graph_path = Path(sub.graph_json_path)
        judge_spec = dict(problem.judge_spec)
        time_limit = int(judge_spec.get("time_limit_seconds", problem.time_limit_seconds))
        test_data_source = (
            Path(problem.hidden_test_data_path) if problem.hidden_test_data_path else None
        )

    try:
        submission_graph = json.loads(graph_path.read_text(encoding="utf-8"))
    except Exception as e:  # noqa: BLE001
        await _finalize(submission_id, status=SubmissionStatus.error, score=None,
                        log=f"Could not load submission graph: {e}",
                        runtime_ms=None, raw=None)
        return

    try:
        result = run_judge(
            submission_id=submission_id,
            submission_graph=submission_graph,
            judge_spec=judge_spec,
            test_data_source=test_data_source,
            timeout_seconds=time_limit,
        )
    except Exception as e:  # noqa: BLE001
        logger.exception("judge crashed for submission %s", submission_id)
        await _finalize(submission_id, status=SubmissionStatus.error, score=None,
                        log=f"Runner crashed: {e}", runtime_ms=None, raw=None)
        return

    status_str = str(result.get("status") or "error")
    try:
        status = SubmissionStatus(status_str)
    except ValueError:
        status = SubmissionStatus.error
    await _finalize(
        submission_id,
        status=status,
        score=float(result.get("score") or 0.0) if status == SubmissionStatus.judged else None,
        log=str(result.get("log") or ""),
        runtime_ms=int(result.get("runtime_ms") or 0),
        raw=result,
    )


async def _finalize(
    submission_id: int,
    *,
    status: SubmissionStatus,
    score: float | None,
    log: str,
    runtime_ms: int | None,
    raw: dict | None,
) -> None:
    async with async_session_maker() as session:
        sub = await session.get(Submission, submission_id)
        if sub is None:
            return
        sub.status = status
        sub.score = score
        sub.judge_log = log
        sub.runtime_ms = runtime_ms
        sub.raw_result = raw
        sub.judge_finished_at = datetime.now(timezone.utc)
        await session.commit()


def run_rq_worker() -> None:
    """Entry point for `python -m app.judge.worker`."""
    from redis import Redis
    from rq import Queue, Worker

    from app.config import get_settings

    settings = get_settings()
    ensure_dir(settings.submissions_dir)
    conn = Redis.from_url(settings.redis_url)
    worker = Worker([Queue("judge", connection=conn)], connection=conn)
    worker.work(with_scheduler=False)


if __name__ == "__main__":
    run_rq_worker()
