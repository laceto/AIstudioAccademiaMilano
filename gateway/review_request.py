"""A customer answers RIESAMINA to a refusal: they ask for a human review.

This is the route the privacy notice promises (human intervention, state your view, contest the
refusal). The message is never a job. It marks the chat's most recent refused request (last 30
days) with `review_requested_at`, atomically and once, and tells Luigi, who sees the usual
Riesamina button. Nothing moves back to review by itself: only Luigi's button or /riesamina does.

A chat can only ever touch its own refused jobs: the lookup filters on the sender's chat id.
"""

from __future__ import annotations

import logging
import re
import unicodedata
from datetime import datetime, timedelta, timezone

from gateway.notify import notify_review_request

logger = logging.getLogger(__name__)

LOOKBACK_DAYS = 30

REPLY_OK = "Ricevuto: il titolare rivedrà la tua richiesta."
REPLY_NONE = "Non ho trovato una tua richiesta rifiutata da far rivedere."
REPLY_ALREADY = "Hai già chiesto il riesame: il titolare rivedrà la tua richiesta."


def is_review_request(text) -> bool:
    """True for exactly RIESAMINA: any case, optional surrounding punctuation or spaces, nothing else."""
    if not isinstance(text, str):
        return False
    folded = unicodedata.normalize("NFKC", text).strip().strip(" \t\r\n.,;:!?\"'()[]*_-").casefold()
    return folded == "riesamina"


def _when(job: dict):
    stamp = job.get("processed_at") or job.get("created_at") or ""
    try:
        when = datetime.fromisoformat(stamp)
    except ValueError:
        return None
    return when if when.tzinfo else when.replace(tzinfo=timezone.utc)


def _latest_refused(store, chat_id) -> dict | None:
    wanted = str(chat_id).strip()
    cutoff = datetime.now(timezone.utc) - timedelta(days=LOOKBACK_DAYS)
    best, best_when = None, None
    for job in store.list_by_status("refused"):
        if str((job.get("metadata") or {}).get("chat_id", "")).strip() != wanted:
            continue
        when = _when(job)
        if when is None or when < cutoff:
            continue
        if best_when is None or when > best_when:
            best, best_when = job, when
    return best


async def handle_review_request(store, chat_id) -> str:
    """Record the request, tell Luigi, and return what the customer is told."""
    try:
        job = _latest_refused(store, chat_id)
    except Exception as exc:
        logger.warning("[review-request] lookup failed: %s", type(exc).__name__)
        return REPLY_NONE
    if job is None:
        return REPLY_NONE
    if job.get("review_requested_at"):
        return REPLY_ALREADY

    # unless_set makes "once only" atomic: of two RIESAMINA messages at once, one wins.
    won = store.transition(
        job["job_id"], "refused",
        {"review_requested_at": datetime.now(timezone.utc).isoformat()},
        unless_set="review_requested_at",
    )
    if won is None:
        return REPLY_ALREADY if (store.get(job["job_id"]) or {}).get("review_requested_at") else REPLY_NONE
    try:  # Luigi's notice failing must not undo the customer's request; /pending still lists it
        await notify_review_request(won, store)
    except Exception as exc:
        logger.warning("[review-request] notify failed for job %s: %s", job["job_id"], type(exc).__name__)
    return REPLY_OK
