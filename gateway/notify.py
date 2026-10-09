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
import logging
import os
import smtplib
import ssl
import time
from collections import deque
from datetime import datetime, timezone
from email.message import EmailMessage

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
    emails = parse_list(os.environ.get("NOTIFY_EMAILS"))
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
