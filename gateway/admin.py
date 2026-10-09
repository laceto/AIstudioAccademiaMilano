"""Luigi's decisions on needs_review jobs.

Pure logic, no Telegram: who may decide, which price is acceptable, the
buttons, and decide() which moves a job from needs_review to approved or
rejected exactly once. gateway/api.py wires it to the Telegram webhook.

Authorisation is the sender's numeric Telegram id, never the @username (a
username can be changed or handed over). ADMIN_TELEGRAM_IDS, or by default
NOTIFY_TELEGRAM_CHAT_IDS, lists the ids; with neither set nobody can decide.
"""

from __future__ import annotations

import math
import os
import re
from dataclasses import dataclass
from datetime import datetime, timezone

from gateway.notify import parse_list

MAX_PRICE = 10_000.0

_ACTIONS = {"approve": "ap", "reject": "rj", "free": "fr", "price": "pr", "send": "sd", "discard": "dc", "retry": "rn"}
_CODES = {v: k for k, v in _ACTIONS.items()}
_CALLBACK_RE = re.compile(r"^(ap|rj|fr|pr|sd|dc|rn):([A-Za-z0-9_-]{1,64})$")
_PRICE_RE = re.compile(r"^\d+(?:[.,]\d+)?$")
_FREE_WORDS = {"gratis", "gratuito", "gratuita", "free"}


# ── who may decide ───────────────────────────────────────────────────────────


def admin_ids() -> list[str]:
    return parse_list(os.environ.get("ADMIN_TELEGRAM_IDS") or os.environ.get("NOTIFY_TELEGRAM_CHAT_IDS"))


def is_admin(user_id) -> bool:
    if user_id is None:
        return False
    return str(user_id).strip().lower() in admin_ids()


# ── prices ───────────────────────────────────────────────────────────────────


def parse_price(raw) -> float | None:
    """"12,50", "EUR 9.90", "gratis" -> float; anything else (negative, NaN, huge, junk) -> None."""
    if not isinstance(raw, str):
        return None
    text = raw.strip().lower()
    if text in _FREE_WORDS:
        return 0.0
    text = re.sub(r"\beur(?:o)?\b", "", text.replace("€", "")).strip()
    if not _PRICE_RE.match(text):
        return None
    value = round(float(text.replace(",", ".")), 2)
    return value if 0 <= value <= MAX_PRICE else None


def proposed_price(job: dict) -> float | None:
    """The catalogue price for the product the classifier picked, or None (unknown product)."""
    from gateway.worker import _PRICES  # lazy: worker imports notify, which this module imports

    product = (job.get("classification") or {}).get("product_type", "unknown_product")
    return _PRICES.get(product)


# ── buttons ──────────────────────────────────────────────────────────────────


def encode_callback(action: str, job_id: str) -> str:
    return f"{_ACTIONS[action]}:{job_id}"  # <= 64 bytes, Telegram's limit


def decode_callback(data) -> tuple[str, str] | None:
    match = _CALLBACK_RE.match(data) if isinstance(data, str) else None
    return (_CODES[match.group(1)], match.group(2)) if match else None


def review_keyboard(job_id: str, price: float | None) -> list[list[dict]]:
    """Telegram inline keyboard (reply_markup.inline_keyboard) for a job awaiting review."""
    first = []
    if price is not None:
        first.append({"text": f"✅ Approva EUR {price:.2f}", "callback_data": encode_callback("approve", job_id)})
    first.append({"text": "\U0001F381 Gratis", "callback_data": encode_callback("free", job_id)})
    second = [
        {"text": "✏️ Imposta prezzo", "callback_data": encode_callback("price", job_id)},
        {"text": "❌ Rifiuta", "callback_data": encode_callback("reject", job_id)},
    ]
    return [first, second]


def result_keyboard(job_id: str) -> list[list[dict]]:
    """Buttons on a finished pipeline result: Luigi reviews before anything reaches the customer."""
    return [[
        {"text": "📤 Invia al cliente", "callback_data": encode_callback("send", job_id)},
        {"text": "🗑 Scarta", "callback_data": encode_callback("discard", job_id)},
    ]]


def retry_keyboard(job_id: str) -> list[list[dict]]:
    """Button on a failed pipeline run."""
    return [[{"text": "🔁 Riprova", "callback_data": encode_callback("retry", job_id)}]]


# ── the decision ─────────────────────────────────────────────────────────────


@dataclass
class Decision:
    ok: bool
    code: str  # approved | rejected | forbidden | not_found | not_pending | already_decided | bad_price | bad_action
    job: dict | None = None


def decide(store, job_id: str, admin_id, action: str, price=None, reason: str = "") -> Decision:
    """Move a needs_review job to approved/rejected, once, if admin_id is allowed to."""
    if not is_admin(admin_id):
        return Decision(False, "forbidden")
    if action not in ("approve", "reject"):
        return Decision(False, "bad_action")
    if action == "approve":
        if isinstance(price, bool) or not isinstance(price, (int, float)):
            return Decision(False, "bad_price")
        if not math.isfinite(price) or not 0 <= price <= MAX_PRICE:
            return Decision(False, "bad_price")

    job = store.get(job_id)
    if job is None:
        return Decision(False, "not_found")
    if job.get("status") in ("approved", "rejected"):
        return Decision(False, "already_decided", job)
    if job.get("status") != "needs_review":
        return Decision(False, "not_pending", job)

    status = "approved" if action == "approve" else "rejected"
    updates = {
        "status": status,
        "decision": {
            "by": str(admin_id).strip(),
            "at": datetime.now(timezone.utc).isoformat(),
            "action": action,
            "reason": reason,
        },
    }
    if action == "approve":
        updates["price"] = round(float(price), 2)

    won = store.transition(job_id, "needs_review", updates)
    if won is not None:
        return Decision(True, status, won)

    # Someone else got there first between our read and the transition.
    latest = store.get(job_id)
    if latest and latest.get("status") in ("approved", "rejected"):
        return Decision(False, "already_decided", latest)
    return Decision(False, "not_pending", latest)


def restart_job(store, job_id: str, admin_id) -> Decision:
    """Put a failed (or never-queued approved) job back in line for the pipeline.

    failed   -> approved, so the worker can claim it again (costs a new run: that is why only Luigi can)
    approved -> unchanged; the caller just queues it again (e.g. the first enqueue failed)
    anything else is refused: a running job must not be run twice, a delivered one is done.
    """
    if not is_admin(admin_id):
        return Decision(False, "forbidden")
    job = store.get(job_id)
    if job is None:
        return Decision(False, "not_found")
    status = job.get("status")
    if status == "approved":
        return Decision(True, "restarted", job)
    if status == "failed":
        won = store.transition(
            job_id, "failed",
            {
                "status": "approved",
                "error": None,
                "restarted_at": datetime.now(timezone.utc).isoformat(),
                "restarted_by": str(admin_id).strip(),
            },
        )
        if won is not None:
            return Decision(True, "restarted", won)
        job = store.get(job_id)
    return Decision(False, "not_restartable", job)


# ── messages ─────────────────────────────────────────────────────────────────


def user_message(job: dict) -> str:
    """What the person who made the request is told. The internal reason is not shared."""
    job_id = job.get("job_id", "?")
    if job.get("status") == "approved":
        price = job.get("price") or 0.0
        cost = "ed è gratuita per questa volta" if price == 0 else f"\nPrezzo: EUR {price:.2f}"
        head = "La tua richiesta è stata approvata"
        return f"{head} {cost}\nJob ID: {job_id}" if price == 0 else f"{head}.{cost}\nJob ID: {job_id}"
    return f"Non possiamo procedere con questa richiesta.\nJob ID: {job_id}"


def pending_jobs(store, limit: int = 10) -> list[dict]:
    return store.list_by_status("needs_review")[:limit]


def job_line(job: dict) -> str:
    """One-line summary of a job for /pending."""
    cls = job.get("classification") or {}
    price = proposed_price(job)
    price_txt = f"EUR {price:.2f}" if price is not None else "prezzo da definire"
    return f"{job.get('job_id', '?')} - {cls.get('summary', job.get('text', '')[:60])} ({price_txt})"
