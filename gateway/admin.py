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
from gateway.retention import expiry_in, retention_days

MAX_PRICE = 10_000.0

_ACTIONS = {"approve": "ap", "reject": "rj", "free": "fr", "price": "pr", "send": "sd", "discard": "dc", "retry": "rn",
            "erase_job": "ej", "erase_chat": "ec", "erase_cancel": "xc"}
_CODES = {v: k for k, v in _ACTIONS.items()}
_CALLBACK_RE = re.compile(r"^(ap|rj|fr|pr|sd|dc|rn|ej|ec|xc):([A-Za-z0-9_-]{1,64})$")
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


def erase_keyboard(action: str, target: str) -> list[list[dict]]:
    """Conferma / Annulla under an erasure card. action: erase_job (target = job id) or erase_chat
    (target = chat id, may be negative). Callback data stays well under Telegram's 64 bytes."""
    return [[
        {"text": "✅ Conferma", "callback_data": encode_callback(action, target)},
        {"text": "↩️ Annulla", "callback_data": encode_callback("erase_cancel", "x")},
    ]]


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


# ── reviewing the pipeline's result ──────────────────────────────────────────
# awaiting_review --send--> delivering --file sent--> delivered
#                                  |--send failed--> awaiting_review (can be tried again)
# awaiting_review --discard--> discarded            (the customer is told nothing)
# Sending reaches a third party, so it is claimed first (delivering) and sent second: two presses
# of the button cannot send the file twice.

_HANDLED = ("delivering", "delivered", "discarded")


def _review_gate(store, job_id: str, admin_id) -> tuple[Decision | None, dict | None]:
    if not is_admin(admin_id):
        return Decision(False, "forbidden"), None
    job = store.get(job_id)
    if job is None:
        return Decision(False, "not_found"), None
    return None, job


def _why_not_reviewable(job: dict | None) -> Decision:
    status = (job or {}).get("status")
    return Decision(False, "already_handled" if status in _HANDLED else "not_reviewable", job)


def begin_delivery(store, job_id: str, admin_id) -> Decision:
    """Claim a finished result for sending (awaiting_review -> delivering). Once only."""
    refusal, job = _review_gate(store, job_id, admin_id)
    if refusal:
        return refusal
    if job.get("status") != "awaiting_review":
        return _why_not_reviewable(job)
    won = store.transition(job_id, "awaiting_review", {"status": "delivering", "delivery_error": None})
    return Decision(True, "delivering", won) if won else _why_not_reviewable(store.get(job_id))


def finish_delivery(store, job_id: str, admin_id) -> dict | None:
    """The file reached the customer (delivering -> delivered)."""
    return store.transition(
        job_id, "delivering",
        {"status": "delivered", "delivered_at": datetime.now(timezone.utc).isoformat(), "delivered_by": str(admin_id).strip()},
    )


def abort_delivery(store, job_id: str, reason: str) -> dict | None:
    """Sending failed: put the result back (delivering -> awaiting_review) so Luigi can try again."""
    return store.transition(job_id, "delivering", {"status": "awaiting_review", "delivery_error": reason})


def discard_result(store, job_id: str, admin_id, reason: str = "") -> Decision:
    """Luigi does not want to send this result (awaiting_review -> discarded)."""
    refusal, job = _review_gate(store, job_id, admin_id)
    if refusal:
        return refusal
    if job.get("status") != "awaiting_review":
        return _why_not_reviewable(job)
    won = store.transition(
        job_id, "awaiting_review",
        {
            "status": "discarded",
            "decision": {
                "by": str(admin_id).strip(),
                "at": datetime.now(timezone.utc).isoformat(),
                "action": "discard",
                "reason": reason,
            },
        },
    )
    return Decision(True, "discarded", won) if won else _why_not_reviewable(store.get(job_id))


def customer_caption(job: dict) -> str:
    """What the customer reads with the file. Nothing internal: no QA verdict, no risk score."""
    price = job.get("price")
    price_txt = "gratuito" if not price else f"EUR {price:.2f}"
    invoice = (job.get("result") or {}).get("invoice_id")
    lines = [
        "Ecco il lavoro che hai richiesto.",
        f"Prezzo: {price_txt}" + (f" (fattura {invoice})" if invoice else ""),
        f"Job ID: {job.get('job_id', '?')}",
    ]
    return "\n".join(lines)


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


def pending_jobs(store, limit: int = 10, status: str = "needs_review") -> list[dict]:
    return store.list_by_status(status)[:limit]


def job_line(job: dict) -> str:
    """One-line summary of a job for /pending."""
    cls = job.get("classification") or {}
    price = job.get("price")  # the price Luigi approved, once there is one
    if price is None:
        price = proposed_price(job)
    price_txt = "gratis" if price == 0 else (f"EUR {price:.2f}" if price is not None else "prezzo da definire")
    return f"{job.get('job_id', '?')} - {cls.get('summary', job.get('text', '')[:60])} ({price_txt})"


# ── refused requests (clearly illegal ones, see gateway/safety.py) ───────────
# refused --Riesamina--> needs_review   (Luigi only, once; then the normal review card follows)
# A refused job is terminal for everyone else: decide() only accepts needs_review, so it can
# never be approved, priced or queued for the pipeline without this explicit step first.
# The callback action is registered here, below the originals, so the tables above stay as they were.

_ACTIONS["reexamine"] = "rx"
_CODES = {v: k for k, v in _ACTIONS.items()}
_CALLBACK_RE = re.compile(r"^(" + "|".join(_ACTIONS.values()) + r"):([A-Za-z0-9_-]{1,64})$")

REFUSED_RECENT_DAYS = 3


def refused_keyboard(job_id: str) -> list[list[dict]]:
    """The one button on a refused request: no approve, no price."""
    return [[{"text": "\U0001F50D Riesamina", "callback_data": encode_callback("reexamine", job_id)}]]


def _chat_of(job: dict) -> str:
    return str((job.get("metadata") or {}).get("chat_id", "")).strip()


def refused_count(store, chat_id) -> int | None:
    """How many refused requests this chat has made (counting the current one). None if unreadable."""
    wanted = str(chat_id).strip()
    if not wanted:
        return None
    try:
        return sum(1 for j in store.list_by_status("refused") if _chat_of(j) == wanted)
    except Exception:
        return None


def refused_category(job: dict) -> str:
    return str((job.get("classification") or {}).get("refuse_reason") or "other")


def recent_refused(store, days: int = REFUSED_RECENT_DAYS, limit: int = 5) -> tuple[list[dict], int]:
    """Refused jobs from the last `days` days, newest first, at most `limit`; plus how many more exist."""
    cutoff = datetime.now(timezone.utc).timestamp() - days * 86400
    recent = []
    for job in store.list_by_status("refused"):
        stamp = job.get("processed_at") or job.get("created_at") or ""
        try:
            when = datetime.fromisoformat(stamp)
            if when.tzinfo is None:
                when = when.replace(tzinfo=timezone.utc)
        except ValueError:
            continue
        if when.timestamp() >= cutoff:
            recent.append((when, job))
    recent.sort(key=lambda pair: pair[0], reverse=True)
    jobs = [job for _, job in recent]
    return jobs[:limit], max(0, len(jobs) - limit)


def refused_line(job: dict) -> str:
    """One line for /pending."""
    text = (job.get("text") or "").replace("\n", " ")[:80]
    asked = " [il cliente chiede il riesame]" if job.get("review_requested_at") else ""
    return f"Rifiutata ({refused_category(job)}){asked}: {job.get('job_id', '?')} - {text}"


_REEXAMINABLE = ("refused", "classified")


def reexamine(store, job_id: str, admin_id) -> Decision:
    """Back to review, once, atomically: refused (Luigi disagrees) or legacy classified (never reviewed)."""
    if not is_admin(admin_id):
        return Decision(False, "forbidden")
    job = store.get(job_id)
    if job is None:
        return Decision(False, "not_found")
    from_status = job.get("status")
    if from_status not in _REEXAMINABLE:
        return Decision(False, "not_refused", job)
    won = store.transition(
        job_id, from_status,
        {
            "status": "needs_review",
            "reexamined": True,  # notify_review then skips the e-mail channel for this job
            "reexamined_by": str(admin_id).strip(),
            "reexamined_at": datetime.now(timezone.utc).isoformat(),
            # back to the normal retention (a refused job is kept for less)
            "expire_at": expiry_in(retention_days()),
        },
    )
    if won is not None:
        return Decision(True, "reexamined", won)
    return Decision(False, "not_refused", store.get(job_id))
