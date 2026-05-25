"""
Mindful Bot — Telegram bot for psychologists and their patients.
Sends daily mindfulness prompts and collects mood check-ins.

Usage:
    python bot.py

Environment:
    TELEGRAM_BOT_TOKEN — set in .env or Railway env vars
"""

from __future__ import annotations

import asyncio
import csv
import json
import logging
import os
import signal
from datetime import datetime
from pathlib import Path

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from dotenv import load_dotenv
from telegram import Update
from telegram.error import Forbidden, NetworkError
from telegram.ext import (
    Application,
    CommandHandler,
    ContextTypes,
    MessageHandler,
    filters,
)

# ---------------------------------------------------------------------------
# Environment & logging
# ---------------------------------------------------------------------------

load_dotenv()

logging.basicConfig(
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
    level=logging.INFO,
)
logger = logging.getLogger("mindful_bot")

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------

BASE_DIR = Path(__file__).parent
DATA_DIR = BASE_DIR / "data"
DATA_DIR.mkdir(exist_ok=True)

SUBSCRIBERS_CSV = DATA_DIR / "subscribers.csv"
MOOD_LOG_CSV = DATA_DIR / "mood_log.csv"
PROMPT_INDEX_JSON = DATA_DIR / "prompt_index.json"

# ---------------------------------------------------------------------------
# Mindfulness prompts (Italian)
# ---------------------------------------------------------------------------

PROMPTS: list[str] = [
    "🌬️ Respira. Inspira per 4 secondi, trattieni per 4, espira per 6. Ripeti 3 volte. Sei nel momento presente.",
    "🌿 Oggi nota una cosa bella che di solito ignori. Un suono, un colore, una sensazione.",
    "💙 Cosa provi adesso nel corpo? Scansiona dalla testa ai piedi, senza giudizio.",
    "☀️ Nomina 3 cose per cui sei grato oggi, anche piccole.",
    "🧘 Fai una pausa di 60 secondi. Nessun telefono, nessun pensiero. Solo respiro.",
    "🌊 I tuoi pensieri sono come onde — arrivano e passano. Osservali senza aggrapparti.",
    "🕯️ Accendi un momento di gentilezza verso te stesso. Cosa ti diresti se fossi il tuo migliore amico?",
    "🌱 Cosa puoi lasciare andare oggi che non ti serve più?",
    "🦋 Il cambiamento è lento e invisibile, come una farfalla nel bozzolo. Abbi pazienza con te stesso.",
    "🌸 Oggi fai una cosa con piena attenzione — anche solo lavare i piatti o bere un caffè.",
]

# ---------------------------------------------------------------------------
# CSV helpers
# ---------------------------------------------------------------------------


def _ensure_subscribers_csv() -> None:
    """Create subscribers CSV with header if it does not exist."""
    if not SUBSCRIBERS_CSV.exists():
        with SUBSCRIBERS_CSV.open("w", newline="", encoding="utf-8") as fh:
            writer = csv.writer(fh)
            writer.writerow(["chat_id", "username", "subscribed_at"])


def _ensure_mood_log_csv() -> None:
    """Create mood log CSV with header if it does not exist."""
    if not MOOD_LOG_CSV.exists():
        with MOOD_LOG_CSV.open("w", newline="", encoding="utf-8") as fh:
            writer = csv.writer(fh)
            writer.writerow(["timestamp", "chat_id", "username", "score", "trigger"])


def _load_subscribers() -> list[dict]:
    """Return list of subscriber dicts from CSV."""
    _ensure_subscribers_csv()
    with SUBSCRIBERS_CSV.open("r", newline="", encoding="utf-8") as fh:
        return list(csv.DictReader(fh))


def _save_subscribers(rows: list[dict]) -> None:
    """Overwrite subscribers CSV with given rows."""
    with SUBSCRIBERS_CSV.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=["chat_id", "username", "subscribed_at"])
        writer.writeheader()
        writer.writerows(rows)


def _is_subscribed(chat_id: int) -> bool:
    rows = _load_subscribers()
    return any(r["chat_id"] == str(chat_id) for r in rows)


def _subscribe(chat_id: int, username: str) -> None:
    if _is_subscribed(chat_id):
        return
    rows = _load_subscribers()
    rows.append(
        {
            "chat_id": str(chat_id),
            "username": username or "",
            "subscribed_at": datetime.now().isoformat(timespec="seconds"),
        }
    )
    _save_subscribers(rows)
    logger.info("Subscribed chat_id=%s username=%s", chat_id, username)


def _unsubscribe(chat_id: int) -> bool:
    rows = _load_subscribers()
    filtered = [r for r in rows if r["chat_id"] != str(chat_id)]
    if len(filtered) == len(rows):
        return False
    _save_subscribers(filtered)
    logger.info("Unsubscribed chat_id=%s", chat_id)
    return True


def _remove_subscriber(chat_id: int) -> None:
    """Silently remove a blocked subscriber."""
    rows = _load_subscribers()
    filtered = [r for r in rows if r["chat_id"] != str(chat_id)]
    if len(filtered) < len(rows):
        _save_subscribers(filtered)
        logger.info("Silently removed unreachable chat_id=%s", chat_id)


def _log_mood(chat_id: int, username: str, score: int, trigger: str) -> None:
    _ensure_mood_log_csv()
    with MOOD_LOG_CSV.open("a", newline="", encoding="utf-8") as fh:
        writer = csv.writer(fh)
        writer.writerow(
            [
                datetime.now().isoformat(timespec="seconds"),
                str(chat_id),
                username or "",
                str(score),
                trigger,
            ]
        )
    logger.info("Mood logged chat_id=%s score=%s trigger=%s", chat_id, score, trigger)


# ---------------------------------------------------------------------------
# Prompt index persistence
# ---------------------------------------------------------------------------


def _load_prompt_index() -> int:
    if PROMPT_INDEX_JSON.exists():
        try:
            data = json.loads(PROMPT_INDEX_JSON.read_text(encoding="utf-8"))
            return int(data.get("index", 0))
        except (json.JSONDecodeError, ValueError):
            pass
    return 0


def _save_prompt_index(index: int) -> None:
    PROMPT_INDEX_JSON.write_text(
        json.dumps({"index": index}), encoding="utf-8"
    )


def _next_prompt() -> str:
    """Return the next prompt and advance the persisted index."""
    idx = _load_prompt_index()
    prompt = PROMPTS[idx % len(PROMPTS)]
    _save_prompt_index(idx + 1)
    return prompt


# ---------------------------------------------------------------------------
# Command handlers
# ---------------------------------------------------------------------------


async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user = update.effective_user
    chat_id = update.effective_chat.id
    username = user.username or user.first_name or ""
    _subscribe(chat_id, username)
    await update.message.reply_text(
        "Benvenuto su Mindful Bot! 🌿\n\n"
        "Sei iscritto ai promemoria quotidiani di mindfulness.\n"
        "Riceverai un messaggio la mattina alle 08:00 e una domanda sul tuo "
        "umore alle 20:00 ogni giorno.\n\n"
        "Usa /help per vedere tutti i comandi disponibili."
    )


async def cmd_stop(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    chat_id = update.effective_chat.id
    removed = _unsubscribe(chat_id)
    if removed:
        await update.message.reply_text(
            "Hai cancellato l'iscrizione. Non riceverai più i promemoria quotidiani. 🌙\n"
            "Puoi riscriverti in qualsiasi momento con /start."
        )
    else:
        await update.message.reply_text(
            "Non risulti iscritto. Usa /start per iscriverti ai promemoria."
        )


async def cmd_help(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text(
        "Ecco i comandi disponibili:\n\n"
        "/start — Iscriviti ai promemoria quotidiani\n"
        "/stop — Cancella l'iscrizione\n"
        "/mood — Registra manualmente il tuo umore (1–5)\n"
        "/help — Mostra questo messaggio di aiuto\n\n"
        "Ogni giorno riceverai:\n"
        "• 08:00 — Un esercizio di mindfulness\n"
        "• 20:00 — Una domanda sul tuo umore serale"
    )


async def cmd_mood(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Initiate a manual mood check-in."""
    context.user_data["awaiting_mood"] = "manual"
    await update.message.reply_text(
        "Come stai oggi? Rispondi con un numero da 1 (male) a 5 (benissimo) 🌿"
    )


async def handle_mood_reply(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle a mood score reply when the bot is waiting for one."""
    if not context.user_data.get("awaiting_mood"):
        return

    text = update.message.text.strip()
    user = update.effective_user
    chat_id = update.effective_chat.id
    username = user.username or user.first_name or ""
    trigger: str = context.user_data["awaiting_mood"]  # "manual" or "scheduled"

    if text in {"1", "2", "3", "4", "5"}:
        score = int(text)
        _log_mood(chat_id, username, score, trigger)
        context.user_data.pop("awaiting_mood", None)

        responses = {
            1: "Mi dispiace. Ricorda che ogni giorno è diverso. Respira. 💙",
            2: "Capito. Prenditi cura di te oggi. 🌿",
            3: "Così così — va bene anche questo. 🌤",
            4: "Bene! Continua così. ☀️",
            5: "Fantastico! Porta questa energia con te. 🌸",
        }
        await update.message.reply_text(responses[score])
    else:
        await update.message.reply_text(
            "Per favore rispondi con un numero da 1 a 5. Riprova:"
        )


# ---------------------------------------------------------------------------
# Scheduled job helpers
# ---------------------------------------------------------------------------


async def _safe_send(bot, chat_id: int, text: str) -> bool:
    """Send a message and return False if the bot was blocked."""
    try:
        await bot.send_message(chat_id=int(chat_id), text=text)
        return True
    except Forbidden:
        logger.warning("Bot blocked by chat_id=%s — removing", chat_id)
        _remove_subscriber(int(chat_id))
        return False
    except NetworkError as exc:
        logger.error("Network error for chat_id=%s: %s", chat_id, exc)
        return False


async def job_morning_prompt(bot) -> None:
    """08:00 daily — send mindfulness prompt to all subscribers."""
    prompt = _next_prompt()
    subscribers = _load_subscribers()
    logger.info("Morning prompt job: %d subscribers", len(subscribers))
    for row in subscribers:
        await _safe_send(bot, row["chat_id"], f"Buongiorno! 🌅\n\n{prompt}")


async def job_evening_mood(bot, app: Application) -> None:
    """20:00 daily — send mood check-in to all subscribers."""
    subscribers = _load_subscribers()
    logger.info("Evening mood job: %d subscribers", len(subscribers))
    for row in subscribers:
        chat_id = int(row["chat_id"])
        sent = await _safe_send(
            bot,
            chat_id,
            "Buonasera 🌙 Come ti senti stasera? Rispondi con un numero da 1 a 5.",
        )
        if sent:
            # Mark the user as awaiting a scheduled mood reply
            # We store this in a bot_data dict keyed by chat_id
            app.bot_data.setdefault("scheduled_mood_pending", set()).add(chat_id)


async def handle_scheduled_mood_reply(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> None:
    """Handle mood replies triggered by the evening scheduled job."""
    chat_id = update.effective_chat.id
    pending: set = context.bot_data.get("scheduled_mood_pending", set())
    if chat_id not in pending:
        return

    text = update.message.text.strip()
    user = update.effective_user
    username = user.username or user.first_name or ""

    if text in {"1", "2", "3", "4", "5"}:
        score = int(text)
        _log_mood(chat_id, username, score, "scheduled")
        pending.discard(chat_id)

        responses = {
            1: "Mi dispiace. Ricorda che ogni giorno è diverso. Respira. 💙",
            2: "Capito. Prenditi cura di te. 🌿",
            3: "Così così — va bene anche questo. 🌤",
            4: "Bene! Continua così. ☀️",
            5: "Fantastico! Porta questa energia con te. 🌸",
        }
        await update.message.reply_text(responses[score])
    else:
        await update.message.reply_text(
            "Per favore rispondi con un numero da 1 a 5:"
        )


# ---------------------------------------------------------------------------
# Application setup
# ---------------------------------------------------------------------------


def build_application(token: str) -> Application:
    app = Application.builder().token(token).build()

    # Commands
    app.add_handler(CommandHandler("start", cmd_start))
    app.add_handler(CommandHandler("stop", cmd_stop))
    app.add_handler(CommandHandler("help", cmd_help))
    app.add_handler(CommandHandler("mood", cmd_mood))

    # Text replies — order matters: manual mood first, then scheduled
    app.add_handler(
        MessageHandler(
            filters.TEXT & ~filters.COMMAND,
            handle_mood_reply,
        )
    )
    app.add_handler(
        MessageHandler(
            filters.TEXT & ~filters.COMMAND,
            handle_scheduled_mood_reply,
        )
    )

    return app


def build_scheduler(app: Application) -> AsyncIOScheduler:
    scheduler = AsyncIOScheduler(timezone="Europe/Rome")

    scheduler.add_job(
        job_morning_prompt,
        trigger=CronTrigger(hour=8, minute=0, timezone="Europe/Rome"),
        args=[app.bot],
        id="morning_prompt",
        replace_existing=True,
        misfire_grace_time=300,
    )

    scheduler.add_job(
        job_evening_mood,
        trigger=CronTrigger(hour=20, minute=0, timezone="Europe/Rome"),
        args=[app.bot, app],
        id="evening_mood",
        replace_existing=True,
        misfire_grace_time=300,
    )

    return scheduler


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------


def main() -> None:
    token = os.environ.get("TELEGRAM_BOT_TOKEN")
    if not token:
        raise RuntimeError(
            "TELEGRAM_BOT_TOKEN is not set. "
            "Copy .env.example to .env and fill in your token."
        )

    app = build_application(token)
    scheduler = build_scheduler(app)

    # Graceful shutdown
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)

    async def _run() -> None:
        scheduler.start()
        logger.info("Scheduler started (timezone=Europe/Rome)")
        async with app:
            await app.initialize()
            await app.start()
            logger.info("Mindful Bot is running. Press Ctrl+C to stop.")
            await app.updater.start_polling(drop_pending_updates=True)

            stop_event = asyncio.Event()

            def _shutdown(signum, frame):  # noqa: ANN001
                logger.info("Signal %s received — shutting down…", signum)
                loop.call_soon_threadsafe(stop_event.set)

            signal.signal(signal.SIGINT, _shutdown)
            signal.signal(signal.SIGTERM, _shutdown)

            await stop_event.wait()

            await app.updater.stop()
            await app.stop()
            scheduler.shutdown(wait=False)
            logger.info("Mindful Bot stopped cleanly.")

    loop.run_until_complete(_run())


if __name__ == "__main__":
    main()
