"""Jobs stuck in `running`: find them, fail them once, tell Luigi once. Never re-run them.

A pipeline run can end without the worker recording it: the container crashed, was killed, or
Cloud Run cut the request at its 900 s limit. The job then stays `running` forever.

Policy (every run costs LLM money, and the first run might still be alive):
  * a job is stale when it is `running` and older than PIPELINE_STALE_SECONDS (default 1200 = the
    900 s request limit plus margin), measured from started_at, else created_at;
  * a stale job is marked `failed` by the atomic store.transition(running -> failed), so a job
    that finishes at the same moment is not clobbered, with swept_at recording who did it;
  * Luigi is told once with the usual failure message and the Riprova button. Only the sweep that
    wins the transition notifies, so repeated sweeps stay quiet;
  * nothing is ever re-run here: only Luigi's Riprova / /run does that.

Late result: if the original worker finishes after the sweeper failed the job, finish_run() lets
it store its (paid) result, but only when the job is still `failed`, was failed by the sweeper, and
its started_at is the one this worker claimed. A job that Luigi has meanwhile restarted is never
touched.

Entry points: POST /sweep on the worker (Cloud Scheduler, every 10 min), /sweep and /pending on
Telegram.
"""

from __future__ import annotations

import logging
import os
from datetime import datetime, timedelta, timezone

logger = logging.getLogger(__name__)

DEFAULT_STALE_SECONDS = 1200


def stale_seconds() -> int:
    """PIPELINE_STALE_SECONDS, or 1200 when unset or not a positive integer."""
    raw = os.environ.get("PIPELINE_STALE_SECONDS", "")
    try:
        value = int(raw)
    except (TypeError, ValueError):
        return DEFAULT_STALE_SECONDS
    return value if value > 0 else DEFAULT_STALE_SECONDS


def _parse(value) -> datetime | None:
    if not isinstance(value, str) or not value.strip():
        return None
    text = value.strip()
    if text.endswith(("Z", "z")):
        text = text[:-1] + "+00:00"
    try:
        parsed = datetime.fromisoformat(text)
    except ValueError:
        return None
    return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)


def running_since(job: dict) -> datetime | None:
    """When the job began running: started_at, else created_at, else unknown (None)."""
    return _parse(job.get("started_at")) or _parse(job.get("created_at"))


def age_seconds(job: dict, now: datetime | None = None) -> float | None:
    since = running_since(job)
    if since is None:
        return None
    return ((now or datetime.now(timezone.utc)) - since).total_seconds()


def is_stale(job: dict, now: datetime | None = None, stale_after: float | None = None) -> bool:
    """Running and older than the limit. A running job with no readable timestamp is stale:
    the worker always writes started_at, so a missing one means the record is damaged."""
    if job.get("status") != "running":
        return False
    age = age_seconds(job, now)
    limit = stale_seconds() if stale_after is None else stale_after
    return age is None or age > limit


def _minutes(seconds: float | None, fallback: float) -> int:
    return max(1, int(round((fallback if seconds is None else seconds) / 60)))


def sweep_stale(store, now: datetime | None = None, stale_after: float | None = None) -> list[dict]:
    """Fail every stale running job. Returns the jobs this call failed (and no others)."""
    now = now or datetime.now(timezone.utc)
    limit = stale_seconds() if stale_after is None else stale_after
    swept = []
    for job in store.list_by_status("running"):
        if not is_stale(job, now, limit):
            continue
        # The listing can be old: another sweep may have failed this job and Luigi restarted it
        # (a fresh run, same job id). Look again right before the transition and skip the job if its
        # run changed or it is no longer stale. This NARROWS the window but is not atomic: the
        # JobStore contract only compares the status, so a restart landing between this get() and
        # the transition() could still be failed. Closing it needs a started_at guard in the store.
        latest = store.get(job["job_id"])
        if latest is None or latest.get("started_at") != job.get("started_at") or not is_stale(latest, now, limit):
            continue
        job = latest
        minutes = _minutes(age_seconds(job, now), limit)
        stamp = now.isoformat()
        won = store.transition(
            job["job_id"], "running",
            {
                "status": "failed",
                "error": f"Interrotta: il worker non ha finito, job fermo da {minutes} minuti",
                "finished_at": stamp,
                "swept_at": stamp,
            },
        )
        if won is not None:  # None = it finished (or was swept) between the listing and now
            logger.warning("[sweep] job %s was running for %d minutes: marked failed", job["job_id"], minutes)
            swept.append(won)
    return swept


async def sweep_and_notify(store, notify, now: datetime | None = None, stale_after: float | None = None) -> list[dict]:
    """sweep_stale, then tell Luigi about each job this call failed (failure message + Riprova)."""
    swept = sweep_stale(store, now=now, stale_after=stale_after)
    for job in swept:
        try:
            await notify(job, {"ok": False, "error": job.get("error")})
        except Exception as exc:  # the job is already failed and shows in /pending
            logger.warning("[sweep] could not notify Luigi about job %s: %s", job.get("job_id"), type(exc).__name__)
    return swept


def finish_run(store, job: dict, updates: dict) -> str:
    """Record the end of a run that the worker claimed (`job` is what its claim returned).

    finished        the normal path: running -> updates
    late            the sweeper failed the job first, this run's good result is kept
    already_failed  the sweeper failed it first and this run failed too: nothing to add, Luigi knows
    superseded      Luigi restarted the job and a newer run owns it: this result is dropped
    lost            anything else (the job is approved again, discarded, ...): nothing written
    """
    job_id, mine = job["job_id"], job.get("started_at")
    for _ in range(2):  # a sweep may land between the read and the transition
        current = store.get(job_id)
        if current is None:
            return "lost"
        status = current.get("status")
        if status == "running":
            # transition() compares only the status: without this look, the newer run of a job that
            # Luigi restarted (also `running`) would be overwritten by this older run. A restart
            # cannot slip in between the look and the transition: it needs the job `failed` first.
            if current.get("started_at") != mine:
                return "superseded"
            if store.transition(job_id, "running", updates) is not None:
                return "finished"
            continue  # swept in between: look again
        if status == "failed" and current.get("swept_at") and current.get("started_at") == mine:
            if updates.get("status") != "awaiting_review":
                return "already_failed"
            if store.transition(job_id, "failed", {**updates, "late_result": True}) is not None:
                return "late"
            continue
        return "lost"
    return "lost"
