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

import asyncio
import logging
import re

from gateway.admin import (
    Decision,
    abort_delivery,
    begin_delivery,
    customer_caption,
    decide,
    decode_callback,
    discard_result,
    encode_callback,
    erase_keyboard,
    finish_delivery,
    is_admin,
    job_line,
    parse_price,
    pending_jobs,
    proposed_price,
    restart_job,
    result_keyboard,
    retry_keyboard,
    review_keyboard,
    user_message,
)
from gateway.convlog import log_message
from gateway.erasure import (
    confirmation_card,
    erase_chat,
    erase_jobs,
    jobs_for_chat,
    make_erasure_log,
    record_erasure,
    result_message,
    parse_chat_target,
    valid_chat_id,
    valid_job_id,
)
from gateway.notify import _safe_filename as safe_filename
from gateway.notify import notify_result
from gateway.pipeline_queue import enqueue_run
from gateway.recovery import age_seconds, is_stale, sweep_and_notify

logger = logging.getLogger(__name__)

PRICE_PROMPT = "Imposta il prezzo per la richiesta (es. 12,50 oppure gratis). Rispondi a questo messaggio.\nJob ID: {job_id}"
_PROMPT_JOB_RE = re.compile(r"Job ID: ([A-Za-z0-9_-]{1,64})")
_COMMANDS = {"/pending", "/approve", "/reject", "/prezzo", "/run", "/file", "/sweep", "/cancella"}
_MAX_PENDING_CARDS = 5
_USAGE = (
    "Uso:\n/pending\n/approve <job_id> [prezzo|gratis]\n/prezzo <job_id> <prezzo>\n/reject <job_id> [motivo]\n"
    "/run <job_id>  (riavvia la pipeline per un job approvato o fallito)\n"
    "/file <job_id>  (rimandami il file di un risultato in attesa di revisione)\n"
    "/sweep  (segna come fallite le run ferme in 'running' da troppo tempo)\n"
    "/cancella <job_id>  oppure  /cancella chat <chat_id>  (cancella i dati di un cliente, dopo conferma)"
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
    if code == "delivering":
        return "Invio in corso"
    if code == "discarded":
        return "Scartato. Il cliente non e' stato avvisato."
    if code == "already_handled":
        return "Già gestito: " + {"delivered": "inviato al cliente", "discarded": "scartato", "delivering": "invio in corso"}.get(
            job.get("status"), str(job.get("status")))
    if code == "not_reviewable":
        return f"Non c'è un risultato da rivedere (stato: {job.get('status', 'sconosciuto')})."
    if code == "restarted":
        return "Riavviata"
    if code == "not_restartable":
        return f"Non si può riavviare (stato: {job.get('status', 'sconosciuto')})."
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


async def _start_pipeline(bot, chat_id, job_id: str) -> None:
    """Queue the approved job for the pipeline worker and tell Luigi how that went.

    The approval already stands whatever happens here: a failure only means nothing started yet,
    and /run <job_id> (or the Riprova button) tries again.
    """
    # enqueue_run is a blocking Google client call: keep it off the event loop
    result = await asyncio.to_thread(enqueue_run, job_id)
    if result.ok:
        text = (f"Il job {job_id} e' gia' in coda." if result.reason == "already_queued"
                else f"Pipeline avviata per il job {job_id}. Ti mando il risultato appena e' pronto.")
    elif result.reason == "not_configured":
        text = f"Approvazione registrata, ma la pipeline non è configurata: per il job {job_id} nessun lavoro è partito."
    else:
        text = (f"Non sono riuscito ad avviare la pipeline per il job {job_id} ({result.reason}). "
                f"L'approvazione resta valida: riprova con /run {job_id}.")
    await _say(bot, chat_id, text)


async def _remove_buttons(bot, chat_id, message: dict) -> None:
    """Strip the inline keyboard from a review card (a document message: only its markup is editable)."""
    try:
        await bot.edit_message_reply_markup(chat_id=chat_id, message_id=message.get("message_id"), reply_markup=None)
    except Exception as exc:
        logger.warning("[delivery] could not remove the buttons: %s", type(exc).__name__)


async def _send_to_customer(bot, store, admin_id, chat_id, message: dict, cb_id: str, job_id: str) -> None:
    """Invia al cliente: claim the result, send the file, record it. A failure puts the result back."""
    decision = begin_delivery(store, job_id, admin_id)
    if not decision.ok:
        await bot.answer_callback_query(cb_id, text=_outcome(decision))
        return

    job = decision.job
    result = job.get("result") or {}
    target = (job.get("metadata") or {}).get("chat_id")
    content = (result.get("content") or "").strip()

    problem = None
    if job.get("channel") != "telegram" or not target:
        problem = "Il cliente non e' su Telegram: non posso inviargli il file da qui. Giralo tu a mano."
    elif not content:
        problem = "Il risultato e' vuoto: niente da inviare."
    if problem:
        abort_delivery(store, job_id, "not_deliverable")
        await bot.answer_callback_query(cb_id, text="Non inviato.")
        await _say(bot, chat_id, f"Job {job_id} non inviato. {problem}")
        return

    try:
        await bot.send_document(
            chat_id=_chat(target),
            document=result["content"].encode("utf-8"),
            filename=safe_filename(result.get("filename")),
            caption=customer_caption(job),
        )
    except Exception as exc:  # e.g. the customer blocked the bot
        abort_delivery(store, job_id, type(exc).__name__)
        logger.warning("[delivery] job %s not delivered: %s", job_id, type(exc).__name__)
        await bot.answer_callback_query(cb_id, text="Invio non riuscito.")
        await _say(
            bot, chat_id,
            f"Non sono riuscito a inviare il file al cliente per il job {job_id} ({type(exc).__name__}). "
            "Il risultato e' di nuovo in attesa: puoi riprovare con il bottone.",
        )
        return

    log_message("out", _chat(target), f"[file] {safe_filename(result.get('filename'))}")
    finish_delivery(store, job_id, admin_id)
    logger.info("[delivery] job %s delivered by %s", job_id, str(admin_id))
    await bot.answer_callback_query(cb_id, text="Inviato al cliente.")
    await _remove_buttons(bot, chat_id, message)
    await _say(bot, chat_id, f"File inviato al cliente (job {job_id}).")


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

    if action in ("erase_job", "erase_chat", "erase_cancel"):
        await _erase_callback(bot, store, from_id, chat_id, message, cb_id, action, job_id)
        return

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

    if action == "retry":
        decision = restart_job(store, job_id, from_id)
        await bot.answer_callback_query(cb_id, text=_outcome(decision))
        if decision.ok:
            await _start_pipeline(bot, chat_id, job_id)
        return

    if action == "send":
        await _send_to_customer(bot, store, from_id, chat_id, message, cb_id, job_id)
        return

    if action == "discard":
        decision = discard_result(store, job_id, from_id)
        await bot.answer_callback_query(cb_id, text=_outcome(decision))
        if decision.ok:
            await _remove_buttons(bot, chat_id, message)
            await _say(bot, chat_id, f"Scartato (job {job_id}). Il cliente non e' stato avvisato.")
        return

    if action == "reject":
        decision, told = await _apply(bot, store, from_id, "reject", job_id)
    elif action in ("approve", "free"):
        price = 0.0 if action == "free" else proposed_price(job)
        decision, told = await _apply(bot, store, from_id, "approve", job_id, price=price)
    else:
        await bot.answer_callback_query(cb_id, text="Azione non valida.")
        return

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
    if decision.ok and action != "reject":
        await _start_pipeline(bot, chat_id, job_id)


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


def _running_line(job: dict) -> str:
    """A job in `running`, with how long it has been going, and a flag when it looks stuck."""
    age = age_seconds(job)
    since = "da un tempo sconosciuto" if age is None else f"da {max(0, int(age // 60))} min"
    line = f"In esecuzione {since}: {job_line(job)}"
    if is_stale(job):
        line += "\nFERMO? Sembra bloccato: /sweep lo segna come fallito (poi puoi usare Riprova)."
    return line


async def _approve_and_report(bot, store, admin_id, chat_id, job_id: str, price) -> None:
    decision, told = await _apply(bot, store, admin_id, "approve", job_id, price=price)
    await _say(bot, chat_id, f"{_outcome(decision)} (job {job_id})")
    if told is False:
        await _say(bot, chat_id, f"Non sono riuscito ad avvisare l'utente per il job {job_id} (ha bloccato il bot?).")
    if decision.ok:
        await _start_pipeline(bot, chat_id, job_id)


async def _run_command(bot, store, admin_id, chat_id, command: str, text: str) -> None:
    if command == "/pending":
        jobs = pending_jobs(store, limit=_MAX_PENDING_CARDS)
        results = pending_jobs(store, limit=_MAX_PENDING_CARDS, status="awaiting_review")
        failures = pending_jobs(store, limit=_MAX_PENDING_CARDS, status="failed")
        running = pending_jobs(store, limit=_MAX_PENDING_CARDS, status="running")
        if not (jobs or results or failures or running):
            await _say(bot, chat_id, "Nessuna richiesta in attesa.")
            return
        for job in jobs:
            await _say(bot, chat_id, job_line(job), reply_markup=_markup(review_keyboard(job["job_id"], proposed_price(job))))
        for job in results:
            await _say(bot, chat_id, f"Risultato da rivedere: {job_line(job)}", reply_markup=_markup(result_keyboard(job["job_id"])))
        for job in failures:
            await _say(bot, chat_id, f"Run fallita: {job_line(job)}\nMotivo: {job.get('error') or 'sconosciuto'}",
                       reply_markup=_markup(retry_keyboard(job["job_id"])))
        for job in running:
            await _say(bot, chat_id, _running_line(job))
        return

    if command == "/sweep":
        swept = await sweep_and_notify(store, notify_result)  # Luigi also gets the failure card with Riprova
        if swept:
            await _say(bot, chat_id, "Segnati come falliti (fermi in 'running'): " + ", ".join(j["job_id"] for j in swept))
        else:
            await _say(bot, chat_id, "Nessun job fermo.")
        return

    if command == "/cancella":
        await _erase_command(bot, store, chat_id, text)
        return

    parts = text.split(maxsplit=2)
    if len(parts) < 2:
        await _say(bot, chat_id, _USAGE)
        return
    job_id = parts[1]

    if command == "/file":
        job = store.get(job_id)
        if job is None or job.get("status") != "awaiting_review" or not job.get("result"):
            await _say(bot, chat_id, f"Nessun risultato in attesa di revisione per il job {job_id}.")
            return
        await notify_result(job, job["result"])
        return

    if command == "/run":
        decision = restart_job(store, job_id, admin_id)
        await _say(bot, chat_id, f"{_outcome(decision)} (job {job_id})")
        if decision.ok:
            await _start_pipeline(bot, chat_id, job_id)
        return

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


# ── erasure on request (/cancella) ───────────────────────────────────────────
# The command only shows a card (counts, statuses, dates: never the customer's text). Deleting
# happens on Conferma, re-checking each job's status at that moment.


async def _show_erase_card(bot, chat_id, scope: str, jobs: list[dict], target: str) -> None:
    """The confirmation card. For a chat the button carries the shown count: <chat_id>_<count>."""
    action = "erase_job" if scope == "job" else "erase_chat"
    if scope == "chat":
        target = f"{target}_{len(jobs)}"
    if len(encode_callback(action, target).encode("utf-8")) > 64:
        await _say(bot, chat_id, "Id troppo lungo per il bottone.\n" + _USAGE)
        return
    await _say(bot, chat_id, confirmation_card(jobs, scope), reply_markup=_markup(erase_keyboard(action, target)))


async def _erase_command(bot, store, chat_id, text: str) -> None:
    args = text.split()[1:]
    if len(args) == 1 and args[0].lower() != "chat" and valid_job_id(args[0]):
        scope, target = "job", args[0]
    elif len(args) == 2 and args[0].lower() == "chat" and valid_chat_id(args[1]):
        scope, target = "chat", args[1].strip()
    else:
        await _say(bot, chat_id, _USAGE)
        return

    if scope == "job":
        if len(encode_callback("erase_job", target).encode("utf-8")) > 64:
            await _say(bot, chat_id, "Id troppo lungo per il bottone.\n" + _USAGE)
            return
        job = store.get(target)
        jobs = [job] if job else []
        if not jobs:
            await _say(bot, chat_id, f"Job {target} non trovato: niente da cancellare.")
            return
    else:
        jobs = jobs_for_chat(store, target)
        if not jobs:
            await _say(bot, chat_id, "Nessun job per questa chat: niente da cancellare.")
            return
    await _show_erase_card(bot, chat_id, scope, jobs, target)


async def _erase_callback(bot, store, admin_id, chat_id, message: dict, cb_id: str, action: str, target: str) -> None:
    """Conferma / Annulla. The caller already proved admin_id is an admin."""
    async def finish(note: str) -> None:  # strip the buttons: the card cannot be pressed again
        try:
            await bot.edit_message_text(chat_id=chat_id, message_id=message.get("message_id"),
                                        text=f"{message.get('text', '')}\n\n{note}")
        except Exception as exc:
            logger.warning("[erasure] could not edit the card: %s", type(exc).__name__)

    if action == "erase_cancel":
        await bot.answer_callback_query(cb_id, text="Annullato.")
        await finish("Annullato. Nessun dato cancellato.")
        return

    scope = "job" if action == "erase_job" else "chat"
    chat_target, expected = (None, None)
    if scope == "chat":
        chat_target, expected = parse_chat_target(target)  # "<chat_id>_<count shown on the card>"
    if not (valid_job_id(target) if scope == "job" else chat_target is not None):
        await bot.answer_callback_query(cb_id, text="Azione non valida.")
        return

    try:
        if scope == "job":
            result = erase_jobs(store, [target], admin_id)
        else:
            result = erase_chat(store, chat_target, admin_id, expected=expected)
    except Exception as exc:  # e.g. the store is down while listing the chat's jobs
        logger.error("[erasure] scope=%s failed before deleting: %s", scope, type(exc).__name__)
        await bot.answer_callback_query(cb_id, text="Errore: non cancellato.", show_alert=True)
        await _say(bot, chat_id, f"Cancellazione non riuscita ({type(exc).__name__}): non ho cancellato nulla. Riprova.")
        return

    if result.code == "changed":
        await bot.answer_callback_query(cb_id, text="I job sono cambiati: nulla cancellato.", show_alert=True)
        await finish("Annullato: i job sono cambiati. Nessun dato cancellato.")
        await _say(bot, chat_id, result_message(result))
        fresh = jobs_for_chat(store, chat_target)
        if fresh:
            await _show_erase_card(bot, chat_id, "chat", fresh, chat_target)
        return

    # Whatever was deleted is recorded, even when some deletions failed.
    record_ok = record_erasure(make_erasure_log(), admin_id, scope, result)
    if result.failed:
        await bot.answer_callback_query(cb_id, text="Alcuni job non sono stati cancellati: ripeti.", show_alert=True)
    elif result.deleted:
        await bot.answer_callback_query(cb_id, text="Cancellato.")
        await finish("Cancellazione eseguita.")
    elif result.refused:
        await bot.answer_callback_query(cb_id, text="Non cancellato: job in corso.", show_alert=True)
    else:
        await bot.answer_callback_query(cb_id, text="Niente da cancellare (gia' fatto?).")
        await finish("Niente da cancellare: gia' cancellato.")
    await _say(bot, chat_id, result_message(result, record_ok))


async def refuse_admin_command(bot, message: dict) -> bool:
    """Used when the update could not be proven to come from Telegram: admin features stay off,
    but a command-looking message is still swallowed (never queued as a job). True = swallowed."""
    text = (message.get("text") or "").strip()
    if not text or text.split()[0].lower().split("@")[0] not in _COMMANDS:
        return False
    chat_id = (message.get("chat") or {}).get("id", (message.get("from") or {}).get("id"))
    await _say(bot, chat_id, "Comando non disponibile.")
    return True
