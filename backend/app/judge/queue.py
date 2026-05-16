"""Job enqueue for judge processing.

Modes (env-controlled):
  OJ_JUDGE_INLINE=true   run the worker function synchronously in-process.
                          Useful for tests and dev without Redis.
  OJ_JUDGE_DISABLED=true skip enqueue entirely. Submission stays in 'queued'.
                          Useful in tests that don't exercise the judge path.

  Otherwise the job is pushed to Redis via RQ.
"""
from __future__ import annotations

import logging
import os

logger = logging.getLogger(__name__)


def _truthy(name: str) -> bool:
    return os.environ.get(name, "").lower() in ("1", "true", "yes", "on")


def enqueue_judge(submission_id: int) -> None:
    if _truthy("OJ_JUDGE_DISABLED"):
        logger.info("judge disabled; skipping submission %s", submission_id)
        return

    if _truthy("OJ_JUDGE_INLINE"):
        from app.judge.worker import judge_submission_sync

        judge_submission_sync(submission_id)
        return

    from redis import Redis
    from rq import Queue

    from app.config import get_settings

    settings = get_settings()
    conn = Redis.from_url(settings.redis_url)
    q = Queue(name="judge", connection=conn)
    q.enqueue("app.judge.worker.judge_submission_sync", submission_id)
