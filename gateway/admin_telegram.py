"""Telegram side of Luigi's approval flow.

gateway/admin.py decides; this module turns Telegram updates into decisions and
tells people the outcome:

  button press  (callback_query)  Approva / Gratis / Imposta prezzo / Rifiuta
  commands      /pending  /approve <id> [prezzo|gratis]  /prezzo <id> <prezzo>  /reject <id> [motivo]
  price answer  Luigi's reply to the "Imposta il prezzo" prompt

Only ids in admin.admin_ids() are obeyed. A command typed by anyone else is
swallowed with "Comando non disponibile" so it never becomes a job request.
The bot object is passed in, so tests drive this with a fake.
"""

from __future__ import annotations

import logging
import re

from gateway.admin import (
    Decision,
    decide,
    decode_callback,
    is_admin,
    job_line,
    parse_price,
    pending_jobs,
    proposed_price,
    review_keyboard,
    user_message,
)
from gateway.convlog import log_message

logger = logging.getLogger(__name__)

PRICE_PROMPT = "Imposta il prezzo per la richiesta (es. 12,50 oppure gratis). Rispondi a questo messaggio.\nJob ID: {job_id}"
_PROMPT_JOB_RE = re.compile(r"Job ID: ([A-Za-z0-9_-]{1,64})")
_COMMANDS = {"/pending", "/approve", "/reject", "/prezzo"}
_MAX_PENDING_CARDS = 5
_USAGE = (
    "Uso:\n/pending\n/approve <job_id> [prezzo|gratis]\n/prezzo <job_id> <prezzo>\n/reject <job_id> [motivo]"
)


# ── small helpers ────────────────────────────────────────────────────────────


def _chat(value):
    """Telegram accepts int or str ids; jobs store them as str, so normalise to int when numeric."""
    text = str(value).strip()
    return int(text) if text.lstrip("-").isdigit() else text


async def _say(bot, chat_id, text: str, **kwargs) -> None:
    log_message("out", chat_id, text)
    await bot.send_message(chat_id=chat_id, text=text, **kwargs)


def _markup(keyboard):
    from telegram import InlineKeyboardButton, InlineKeyboardMarkup

    return InlineKeyboardMarkup(
        [[InlineKeyboardButton(text=b["text"], callback_data=b["callback_data"]) for b in row] for row in keyboard]
    )


def _outcome(decision: Decision) -> str:
    """One line for Luigi describing what happened."""
    code = decision.code
    job = decision.job or {}
    if code == "approved":
        price = job.get("price") or 0.0
        return "Approvata: gratis" if price == 0 else f"Approvata: EUR {price:.2f}"
    if code == "rejected":
        return "Rifiutata"
    if code == "already_decided":
        return "Già deciso: " + ("approvata" if job.get("status") == "approved" else "rifiutata")
    if code == "not_found":
        return "Richiesta non trovata."
    if code == "not_pending":
        return "Questa richiesta non è in attesa di revisione."
    if code == "bad_price":
        return "Prezzo non valido o non disponibile: usa Imposta prezzo."
    if code == "forbidden":
        return "Non autorizzato."
    return "Azione non valida."


async def _tell_the_user(bot, job: dict) -> bool | None:
    """Send the outcome to whoever made the request. None = no Telegram chat to write to."""
    chat_id = (job.get("metadata") or {}).get("chat_id")
    if job.get("channel") != "telegram" or not chat_id:
        return None
    try:
        await _say(bot, _chat(chat_id), user_message(job))
        return True
    except Exception as exc:  # the bot may be blocked; the decision already stands
        logger.warning("[approval] could not tell the user about job %s: %s", job.get("job_id"), type(exc).__name__)
        return False


async def _apply(bot, store, admin_id, action: str, job_id: str, price=None, reason: str = "") -> tuple[Decision, bool | None]:
    decision = decide(store, job_id, admin_id, action, price=price, reason=reason)
    told = None
    if decision.ok:
        logger.info(
            "[approval] job %s -> %s by %s price=%s", job_id, decision.code, str(admin_id), decision.job.get("price")
        )
        told = await _tell_the_user(bot, decision.job)
    return decision, told


# ── button presses ───────────────────────────────────────────────────────────


async def handle_callback(bot, store, callback: dict) -> None:
    cb_id = callback.get("id")
    from_id = (callback.get("from") or {}).get("id")
    message = callback.get("message") or {}
    chat_id = (message.get("chat") or {}).get("id", from_id)

    parsed = decode_callback(callback.get("data"))
    if parsed is None:
        await bot.answer_callback_query(cb_id, text="Azione non valida.")
        return
    if not is_admin(from_id):
        logger.warning("[approval] refused a button press from %s", from_id)
        await bot.answer_callback_query(cb_id, text="Non autorizzato.", show_alert=True)
        return

    action, job_id = parsed

    job = store.get(job_id)
    if job is None:
        await bot.answer_callback_query(cb_id, text=_outcome(Decision(False, "not_found")))
        return

    if action == "price":
        await bot.answer_callback_query(cb_id)
        from telegram import ForceReply

        await _say(
            bot, chat_id, PRICE_PROMPT.format(job_id=job_id),
            reply_markup=ForceReply(input_field_placeholder="12,50 oppure gratis"),
        )
        return

    if action == "reject":
        decision, told = await _apply(bot, store, from_id, "reject", job_id)
    else:
        price = 0.0 if action == "free" else proposed_price(job)
        decision, told = await _apply(bot, store, from_id, "approve", job_id, price=price)

    text = _outcome(decision)
    await bot.answer_callback_query(cb_id, text=text)

    # Replace the card's buttons with the outcome, so it cannot be pressed twice.
    if decision.ok or decision.code == "already_decided":
        try:
            await bot.edit_message_text(
                chat_id=chat_id, message_id=message.get("message_id"),
                text=f"{message.get('text', '')}\n\n{text}",
            )
        except Exception as exc:
            logger.warning("[approval] could not edit the card for job %s: %s", job_id, type(exc).__name__)
    if told is False:
        await _say(bot, chat_id, f"Non sono riuscito ad avvisare l'utente per il job {job_id} (ha bloccato il bot?).")


# ── commands and the price answer ────────────────────────────────────────────


async def handle_admin_message(bot, store, message: dict) -> bool:
    """Handle admin commands and price answers. True = handled, the normal flow must not run."""
    text = (message.get("text") or "").strip()
    from_id = (message.get("from") or {}).get("id")
    chat_id = (message.get("chat") or {}).get("id", from_id)
    if not text:
        return False

    command = text.split()[0].lower().split("@")[0]
    if command in _COMMANDS:
        if not is_admin(from_id):
            await _say(bot, chat_id, "Comando non disponibile.")
            return True
        await _run_command(bot, store, from_id, chat_id, command, text)
        return True

    replied = message.get("reply_to_message")
    if replied and is_admin(from_id) and "Imposta il prezzo" in (replied.get("text") or ""):
        match = _PROMPT_JOB_RE.search(replied["text"])
        if match:
            price = parse_price(text)
            if price is None:
                await _say(bot, chat_id, "Prezzo non valido: scrivi un numero (es. 12,50) oppure gratis.")
            else:
                await _approve_and_report(bot, store, from_id, chat_id, match.group(1), price)
            return True
    return False


async def _approve_and_report(bot, store, admin_id, chat_id, job_id: str, price) -> None:
    decision, told = await _apply(bot, store, admin_id, "approve", job_id, price=price)
    await _say(bot, chat_id, f"{_outcome(decision)} (job {job_id})")
    if told is False:
        await _say(bot, chat_id, f"Non sono riuscito ad avvisare l'utente per il job {job_id} (ha bloccato il bot?).")


async def _run_command(bot, store, admin_id, chat_id, command: str, text: str) -> None:
    if command == "/pending":
        jobs = pending_jobs(store, limit=_MAX_PENDING_CARDS)
        if not jobs:
            await _say(bot, chat_id, "Nessuna richiesta in attesa.")
            return
        for job in jobs:
            await _say(bot, chat_id, job_line(job), reply_markup=_markup(review_keyboard(job["job_id"], proposed_price(job))))
        return

    parts = text.split(maxsplit=2)
    if len(parts) < 2:
        await _say(bot, chat_id, _USAGE)
        return
    job_id = parts[1]

    if command == "/reject":
        decision, told = await _apply(bot, store, admin_id, "reject", job_id, reason=parts[2] if len(parts) > 2 else "")
        await _say(bot, chat_id, f"{_outcome(decision)} (job {job_id})")
        if told is False:
            await _say(bot, chat_id, f"Non sono riuscito ad avvisare l'utente per il job {job_id} (ha bloccato il bot?).")
        return

    # /approve and /prezzo
    if len(parts) > 2:
        price = parse_price(parts[2])
        if price is None:
            await _say(bot, chat_id, "Prezzo non valido: scrivi un numero (es. 12,50) oppure gratis.")
            return
    elif command == "/prezzo":
        await _say(bot, chat_id, _USAGE)
        return
    else:
        job = store.get(job_id)
        if job is None:
            await _say(bot, chat_id, "Richiesta non trovata.")
            return
        price = proposed_price(job)
        if price is None:
            await _say(bot, chat_id, "Questo prodotto non ha un prezzo a catalogo: usa /approve <job_id> <prezzo|gratis>.")
            return
    await _approve_and_report(bot, store, admin_id, chat_id, job_id, price)


async def refuse_admin_command(bot, message: dict) -> bool:
    """Used when the update could not be proven to come from Telegram: admin features stay off,
    but a command-looking message is still swallowed (never queued as a job). True = swallowed."""
    text = (message.get("text") or "").strip()
    if not text or text.split()[0].lower().split("@")[0] not in _COMMANDS:
        return False
    chat_id = (message.get("chat") or {}).get("id", (message.get("from") or {}).get("id"))
    await _say(bot, chat_id, "Comando non disponibile.")
    return True
