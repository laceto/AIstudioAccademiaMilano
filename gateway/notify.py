"""Notify Luigi when a job needs review.

A job lands in `needs_review` when the classifier is unsure or the product is
not in the catalogue. Until now nobody was told. notify_review() sends:

  - a plain-text Telegram message to every id in NOTIFY_TELEGRAM_CHAT_IDS
  - an email to every address in NOTIFY_EMAILS (one message each, so the
    recipients do not see one another)

Each channel is optional and isolated: a failure in one never blocks the other
and never breaks the reply the user gets. Failures are logged by exception type
only — the Telegram error text contains the bot token in its URL and SMTP errors
can echo credentials.

Config (env):
    NOTIFY_EMAILS             comma separated list of addresses
    NOTIFY_TELEGRAM_CHAT_IDS  comma separated numeric ids (not @usernames)
    TELEGRAM_BOT_TOKEN        reused from the gateway
    SMTP_HOST / SMTP_PORT     default smtp.gmail.com / 587 (STARTTLS)
    SMTP_USER / SMTP_PASSWORD Gmail app password, from Secret Manager
    NOTIFY_FROM               default SMTP_USER

Guards are per instance (Cloud Run scales to zero), so they are best-effort:
the same job is notified once, and at most MAX_PER_WINDOW notifications go out
per WINDOW_SEC so a flood of requests cannot flood Luigi.
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import re
import smtplib
import ssl
import time
from collections import deque
from datetime import datetime, timezone
from email.message import EmailMessage
from pathlib import Path

import httpx

logger = logging.getLogger(__name__)

MAX_TEXT = 500
MAX_PER_WINDOW = 10
WINDOW_SEC = 60.0

_notified: set[str] = set()
_recent: deque[float] = deque()


def _reset_state() -> None:
    """Clear the per-instance guards (tests)."""
    _notified.clear()
    _notified_refusals.clear()
    _recent_refusals.clear()
    _recent.clear()


def parse_list(value: str | None) -> list[str]:
    """Split a comma separated env value: trimmed, lower-cased, de-duplicated, order kept."""
    out: list[str] = []
    for item in (value or "").split(","):
        item = item.strip().lower()
        if item and item not in out:
            out.append(item)
    return out


def build_message(job: dict) -> tuple[str, str]:
    """Return (subject, body) describing a job for Luigi. Plain text, user text truncated."""
    from gateway.worker import _PRICES  # lazy: worker imports this module

    cls = job.get("classification") or {}
    meta = job.get("metadata") or {}
    product = cls.get("product_type", "unknown_product")
    price = _PRICES.get(product)
    price_txt = f"EUR {price:.2f}" if price is not None else "da definire"

    text = (job.get("text") or "").replace("\r", "")
    truncated = len(text) > MAX_TEXT
    text = text[:MAX_TEXT]
    if truncated:
        text += f"\n[troncato: testo originale di {len(job.get('text') or '')} caratteri]"

    job_id = job.get("job_id", "?")
    subject = f"[AI Studio] Richiesta da rivedere - job {job_id}"
    body = "\n".join(
        [
            "Richiesta da rivedere",
            "",
            f"Job ID: {job_id}",
            f"Canale: {job.get('channel', '?')}",
            f"Utente (chat): {meta.get('chat_id', '?')}",
            f"Ora (UTC): {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S')}",
            "",
            f"Riassunto: {cls.get('summary', '-')}",
            f"Prodotto: {product}",
            f"Prezzo proposto: {price_txt}",
            f"Confidenza: {cls.get('confidence', '-')}",
            "",
            "Testo dell'utente:",
            text,
        ]
    )
    return subject, body


async def _send_telegram(chat_ids: list[str], text: str, buttons: list[list[dict]] | None = None) -> None:
    """Send plain text (no parse_mode: the text contains user input) to each chat id.

    `buttons` is an inline keyboard (rows of {"text", "callback_data"}); see gateway/admin.py.
    """
    token = os.environ.get("TELEGRAM_BOT_TOKEN", "")
    if not token:
        raise RuntimeError("TELEGRAM_BOT_TOKEN not configured")
    failed = 0
    async with httpx.AsyncClient(timeout=10.0) as client:
        for chat_id in chat_ids:
            payload: dict = {"chat_id": chat_id, "text": text}
            if buttons:
                payload["reply_markup"] = {"inline_keyboard": buttons}
            resp = await client.post(f"https://api.telegram.org/bot{token}/sendMessage", json=payload)
            if resp.status_code != 200:
                failed += 1
    if failed:
        raise RuntimeError(f"telegram: {failed}/{len(chat_ids)} sends failed")


def _send_email(recipients: list[str], subject: str, body: str) -> None:
    """Send one message per recipient over SMTP with STARTTLS (blocking: run in a thread)."""
    user = os.environ.get("SMTP_USER", "")
    password = os.environ.get("SMTP_PASSWORD", "")
    if not user or not password:
        raise RuntimeError("SMTP credentials not configured")
    host = os.environ.get("SMTP_HOST", "smtp.gmail.com")
    port = int(os.environ.get("SMTP_PORT", "587"))
    sender = os.environ.get("NOTIFY_FROM", user)

    with smtplib.SMTP(host, port, timeout=15) as smtp:
        smtp.starttls(context=ssl.create_default_context())
        smtp.login(user, password)
        for recipient in recipients:
            msg = EmailMessage()
            msg["From"] = sender
            msg["To"] = recipient
            msg["Subject"] = subject
            msg.set_content(body)
            smtp.send_message(msg)


def _allow(job_id: str) -> str | None:
    """Return None if this job may be notified now, else the reason it is skipped."""
    if job_id in _notified:
        return "duplicate"
    now = time.monotonic()
    while _recent and now - _recent[0] > WINDOW_SEC:
        _recent.popleft()
    if len(_recent) >= MAX_PER_WINDOW:
        return "rate_limited"
    return None


async def notify_review(job: dict) -> dict:
    """Notify Luigi about a needs_review job. Returns a per-channel outcome dict.

    {} when nothing is configured, {"skipped": reason} when guarded, otherwise
    {"telegram": "sent"|"failed", "email": "sent"|"failed"} for configured channels.
    """
    chat_ids = parse_list(os.environ.get("NOTIFY_TELEGRAM_CHAT_IDS"))
    # A request Luigi pulled back from a refusal goes to Telegram only: e-mail would copy possibly
    # illegal or third-party data into Gmail.
    emails = [] if job.get("reexamined") else parse_list(os.environ.get("NOTIFY_EMAILS"))
    if not chat_ids and not emails:
        return {}

    job_id = str(job.get("job_id", ""))
    reason = _allow(job_id)
    if reason:
        logger.info("[notify] job %s skipped (%s)", job_id, reason)
        return {"skipped": reason}
    _notified.add(job_id)
    _recent.append(time.monotonic())

    subject, body = build_message(job)
    channels: dict[str, object] = {}
    if chat_ids:
        from gateway.admin import proposed_price, review_keyboard  # lazy: admin imports this module

        buttons = review_keyboard(job_id, proposed_price(job))
        channels["telegram"] = _send_telegram(chat_ids, f"{subject}\n\n{body}", buttons=buttons)
    if emails:
        channels["email"] = asyncio.to_thread(_send_email, emails, subject, body)

    results = await asyncio.gather(*channels.values(), return_exceptions=True)
    outcome: dict[str, str] = {}
    for name, res in zip(channels, results):
        if isinstance(res, BaseException):
            # type only: the message can hold the bot token (URL) or SMTP credentials
            logger.warning("[notify] %s failed for job %s: %s", name, job_id, type(res).__name__)
            outcome[name] = "failed"
        else:
            logger.info("[notify] %s sent for job %s", name, job_id)
            outcome[name] = "sent"
    return outcome


# ── the pipeline's result goes to Luigi first ────────────────────────────────

MAX_CAPTION = 1000  # Telegram allows 1024 characters in a document caption
_FILENAME_RE = re.compile(r"[^A-Za-z0-9._-]")


def _safe_filename(name: str | None) -> str:
    base = _FILENAME_RE.sub("_", Path(name or "").name)
    return base.strip(".") and base or "deliverable.txt"


def _price_text(price) -> str:
    return "n/d" if price is None else ("gratis" if price == 0 else f"EUR {price:.2f}")


def _caption(job: dict, result: dict) -> str:
    kb = len((result.get("content") or "").encode("utf-8")) / 1024
    risk = "RISCHIO ALTO" if result.get("high_risk") else "rischio ok"
    lines = [
        f"Risultato pronto - job {job.get('job_id', '?')}",
        f"Richiesta: {(job.get('text') or '')[:200]}",
        f"Prodotto: {result.get('product_type')} | Prezzo: {_price_text(result.get('price'))}",
        f"QA: {'superata' if result.get('qa_passed') else 'NON superata'} | Rischio: {result.get('risk_score', 0.0):.1f}/5 ({risk})",
        f"File: {_safe_filename(result.get('filename'))} ({kb:.1f} KB)",
        f"Cliente: chat {(job.get('metadata') or {}).get('chat_id') or '-'}",
    ]
    return "\n".join(lines)[:MAX_CAPTION]


def _failure_text(job: dict, result: dict) -> str:
    return (
        f"La pipeline non e' riuscita - job {job.get('job_id', '?')}\n"
        f"Richiesta: {(job.get('text') or '')[:200]}\n"
        f"Motivo: {result.get('error') or 'sconosciuto'}"
    )


async def _send_document(chat_ids: list[str], caption: str, filename: str, content: bytes, buttons) -> None:
    """Send a file (multipart) with an inline keyboard to each chat id."""
    token = os.environ.get("TELEGRAM_BOT_TOKEN", "")
    if not token:
        raise RuntimeError("TELEGRAM_BOT_TOKEN not configured")
    failed = 0
    async with httpx.AsyncClient(timeout=30.0) as client:
        for chat_id in chat_ids:
            resp = await client.post(
                f"https://api.telegram.org/bot{token}/sendDocument",
                data={"chat_id": chat_id, "caption": caption, "reply_markup": json.dumps({"inline_keyboard": buttons})},
                files={"document": (filename, content, "text/plain")},
            )
            if resp.status_code != 200:
                failed += 1
    if failed:
        raise RuntimeError(f"telegram: {failed}/{len(chat_ids)} document sends failed")


async def notify_result(job: dict, result: dict) -> dict:
    """Send Luigi the pipeline's output (a file with Invia/Scarta buttons) or its failure (with Riprova).

    Telegram only: the file is the thing to review. Returns {} when no admin id is configured,
    otherwise {"telegram": "sent" | "failed"}. Never raises; errors are logged by type only.
    """
    chat_ids = parse_list(os.environ.get("NOTIFY_TELEGRAM_CHAT_IDS"))
    if not chat_ids:
        return {}
    from gateway.admin import result_keyboard, retry_keyboard  # lazy: admin imports this module

    job_id = job.get("job_id", "?")
    try:
        if result.get("ok"):
            await _send_document(
                chat_ids, _caption(job, result), _safe_filename(result.get("filename")),
                (result.get("content") or "").encode("utf-8"), result_keyboard(job_id),
            )
        else:
            await _send_telegram(chat_ids, _failure_text(job, result), buttons=retry_keyboard(job_id))
    except Exception as exc:
        logger.warning("[notify] result for job %s not delivered: %s", job_id, type(exc).__name__)
        return {"telegram": "failed"}
    logger.info("[notify] result for job %s sent to Luigi", job_id)
    return {"telegram": "sent"}


# ── refused requests: told to Luigi, never queued for approval ───────────────

MAX_REFUSED_TEXT = 200
_notified_refusals: set[str] = set()
# Refusals have their OWN rate window: a flood of refused requests must never suppress a real
# review notice (the shared _recent window above is for notify_review only).
_recent_refusals: deque[float] = deque()


def build_refusal_message(job: dict, count: int | None) -> str:
    """Plain text for Luigi: what was refused and why (category), how often this chat did it."""
    from gateway.admin import refused_category  # lazy: admin imports this module

    meta = job.get("metadata") or {}
    job_id = job.get("job_id", "?")
    times = "?" if count is None else str(count)
    text = (job.get("text") or "").replace("\r", "")[:MAX_REFUSED_TEXT]
    return "\n".join(
        [
            f"Richiesta rifiutata automaticamente - job {job_id}",
            f"Categoria (automatica, non verificata): {refused_category(job)}",
            f"Cliente: chat {meta.get('chat_id', '?')} - richieste rifiutate da questa chat: {times}",
            "",
            "Testo:",
            text,
            "",
            f"Se e' un errore premi Riesamina (o /riesamina {job_id}): torna in revisione e potrai approvarla.",
        ]
    )


async def notify_refusal(job: dict, store=None) -> dict:
    """Tell Luigi about an automatically refused request. Telegram only, no approve/price buttons.

    One button, Riesamina. No e-mail: a refusal is not a request to act on. Returns {} when no admin
    id is configured, {"skipped": reason} when guarded, otherwise {"telegram": "sent"|"failed"}.
    Never raises; errors are logged by type only.
    """
    chat_ids = parse_list(os.environ.get("NOTIFY_TELEGRAM_CHAT_IDS"))
    if not chat_ids:
        return {}
    from gateway.admin import refused_count, refused_keyboard  # lazy: admin imports this module

    job_id = str(job.get("job_id", ""))
    if job_id in _notified_refusals:
        return {"skipped": "duplicate"}
    now = time.monotonic()
    while _recent_refusals and now - _recent_refusals[0] > WINDOW_SEC:
        _recent_refusals.popleft()
    if len(_recent_refusals) >= MAX_PER_WINDOW:
        logger.info("[notify] refusal %s skipped (rate_limited); /pending still lists it", job_id)
        return {"skipped": "rate_limited"}
    _notified_refusals.add(job_id)
    _recent_refusals.append(now)

    count = refused_count(store, (job.get("metadata") or {}).get("chat_id", "")) if store is not None else None
    try:
        await _send_telegram(chat_ids, build_refusal_message(job, count), buttons=refused_keyboard(job_id))
    except Exception as exc:
        logger.warning("[notify] refusal for job %s not delivered: %s", job_id, type(exc).__name__)
        return {"telegram": "failed"}
    logger.info("[notify] refusal for job %s sent to Luigi", job_id)
    return {"telegram": "sent"}


def build_review_request_message(job: dict, count: int | None) -> str:
    """Luigi's message when the customer answers RIESAMINA: same style as the refusal notice."""
    lines = build_refusal_message(job, count).split("\n")
    lines[0] = f"Il cliente chiede il riesame - job {job.get('job_id', '?')}"
    return "\n".join(lines)


async def notify_review_request(job: dict, store=None) -> dict:
    """Tell Luigi the customer asked for a human review of a refusal (Telegram, Riesamina button).

    Does not move the job: only Luigi's button or /riesamina does. Shares the refusal rate window.
    Never raises; errors are logged by type only.
    """
    chat_ids = parse_list(os.environ.get("NOTIFY_TELEGRAM_CHAT_IDS"))
    if not chat_ids:
        return {}
    from gateway.admin import refused_count, refused_keyboard  # lazy: admin imports this module

    job_id = str(job.get("job_id", ""))
    now = time.monotonic()
    while _recent_refusals and now - _recent_refusals[0] > WINDOW_SEC:
        _recent_refusals.popleft()
    if len(_recent_refusals) >= MAX_PER_WINDOW:
        logger.info("[notify] review request %s skipped (rate_limited); /pending still lists it", job_id)
        return {"skipped": "rate_limited"}
    _recent_refusals.append(now)

    count = refused_count(store, (job.get("metadata") or {}).get("chat_id", "")) if store is not None else None
    try:
        await _send_telegram(chat_ids, build_review_request_message(job, count), buttons=refused_keyboard(job_id))
    except Exception as exc:
        logger.warning("[notify] review request for job %s not delivered: %s", job_id, type(exc).__name__)
        return {"telegram": "failed"}
    return {"telegram": "sent"}
