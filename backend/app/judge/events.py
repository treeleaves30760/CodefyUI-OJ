"""Pub/sub bridge between the judge worker and any SSE subscribers.

The worker calls :func:`publish_contest_update` once a submission attached to
a contest is finalized — that publishes a tiny JSON envelope to a Redis
channel namespaced by contest id. The leaderboard SSE handler subscribes to
the same channel via :func:`subscribe_contest_updates` and pushes a refreshed
leaderboard to every connected browser.

Falls back to a no-op when Redis is unreachable so dev runs without Redis
(``OJ_JUDGE_INLINE=true``) still work — clients just get the periodic poll
fallback the frontend already implements. Tests can also set
``OJ_EVENTS_DISABLED=true`` to bypass redis entirely.
"""
from __future__ import annotations

import asyncio
import json
import logging
import os
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

logger = logging.getLogger(__name__)


def _channel(contest_id: int) -> str:
    return f"oj:contest:{contest_id}:updates"


def _events_disabled() -> bool:
    return os.environ.get("OJ_EVENTS_DISABLED", "").lower() in ("1", "true", "yes", "on")


def publish_contest_update(contest_id: int, *, reason: str = "submission") -> None:
    """Synchronous publish — called from the worker after _finalize."""
    if _events_disabled():
        return
    try:
        from redis import Redis  # local import — keeps API boot fast if redis is absent

        from app.config import get_settings

        settings = get_settings()
        conn = Redis.from_url(settings.redis_url, socket_connect_timeout=1)
        try:
            conn.publish(
                _channel(contest_id),
                json.dumps({"contest_id": contest_id, "reason": reason}),
            )
        finally:
            try:
                conn.close()
            except Exception:  # noqa: BLE001
                pass
    except Exception as e:  # noqa: BLE001
        # Pub/sub is best-effort; don't fail the judge run if Redis is down.
        logger.warning("publish_contest_update(%s) failed: %s", contest_id, e)


async def _noop_stream() -> AsyncIterator[dict]:
    """A stream that never yields — used when Redis is unavailable.

    The SSE loop owns its own keepalive timer; consumers just see updates
    never arrive and the connection stays alive on heartbeat.
    """
    while True:
        await asyncio.sleep(3600)
        if False:  # pragma: no cover - presence makes this a generator
            yield {}


@asynccontextmanager
async def subscribe_contest_updates(
    contest_id: int,
) -> AsyncIterator[AsyncIterator[dict]]:
    """Async iterator yielding pub/sub messages for one contest.

    Used as ``async with subscribe_contest_updates(cid) as stream: async for msg in stream:``.
    Yields parsed JSON envelopes. Gracefully returns an empty iterator when
    Redis can't be reached.
    """
    if _events_disabled():
        yield _noop_stream()
        return

    try:
        from redis.asyncio import Redis  # type: ignore[import-not-found]

        from app.config import get_settings

        settings = get_settings()
        conn = Redis.from_url(
            settings.redis_url,
            decode_responses=True,
            socket_connect_timeout=1,
        )
        pubsub = conn.pubsub()
        await pubsub.subscribe(_channel(contest_id))
    except Exception as e:  # noqa: BLE001
        logger.warning("subscribe_contest_updates(%s) unavailable: %s", contest_id, e)
        yield _noop_stream()
        return

    async def _drain() -> AsyncIterator[dict]:
        while True:
            msg = await pubsub.get_message(ignore_subscribe_messages=True, timeout=None)
            if msg is None:
                continue
            data = msg.get("data")
            if isinstance(data, (bytes, bytearray)):
                data = data.decode("utf-8", errors="replace")
            if not isinstance(data, str):
                continue
            try:
                yield json.loads(data)
            except json.JSONDecodeError:
                yield {"raw": data}

    try:
        yield _drain()
    finally:
        try:
            await pubsub.unsubscribe(_channel(contest_id))
            await pubsub.aclose()
            await conn.aclose()
        except Exception:  # noqa: BLE001
            pass


__all__ = ["publish_contest_update", "subscribe_contest_updates"]
