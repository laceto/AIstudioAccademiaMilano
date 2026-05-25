"""
Mindful Bot - adaptive Telegram bot for psychologists and their patients.

Adapts to user profile (adult / child / night-worker) collected during
onboarding, and sends prompts at each user's personal wake time.

Environment:
    TELEGRAM_BOT_TOKEN - set in .env or Railway env vars
"""

from __future__ import annotations

import asyncio
import csv
import logging
import os
import signal
from datetime import datetime
from pathlib import Path
from typing import Optional

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.interval import IntervalTrigger
from dotenv import load_dotenv
from telegram import ReplyKeyboardMarkup, ReplyKeyboardRemove, Update
from telegram.error import Forbidden, NetworkError
from telegram.ext import (
    Application,
    CommandHandler,
    ContextTypes,
    ConversationHandler,
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
MOOD_LOG_CSV    = DATA_DIR / "mood_log.csv"

# ---------------------------------------------------------------------------
# Onboarding conversation states
# ---------------------------------------------------------------------------

ASK_PROFILE, ASK_WAKE_HOUR = range(2)

PROFILE_ADULT = "adult"
PROFILE_CHILD = "child"
PROFILE_NIGHT = "night_worker"

_PROFILE_LABELS = {
    PROFILE_ADULT: "Adulto",
    PROFILE_CHILD: "Bambino",
    PROFILE_NIGHT: "Turno notturno",
}

# ---------------------------------------------------------------------------
# Prompt libraries (Italian) — one per profile
# ---------------------------------------------------------------------------

PROMPTS: dict[str, list[str]] = {
    PROFILE_ADULT: [
        "Respira. Inspira per 4 secondi, trattieni per 4, espira per 6. Ripeti 3 volte.",
        "Oggi nota una cosa bella che di solito ignori. Un suono, un colore, una sensazione.",
        "Cosa provi adesso nel corpo? Scansiona dalla testa ai piedi, senza giudizio.",
        "Nomina 3 cose per cui sei grato oggi, anche piccole.",
        "Fai una pausa di 60 secondi. Nessun telefono. Solo respiro.",
        "I tuoi pensieri sono come onde: arrivano e passano. Osservali senza aggrapparti.",
        "Cosa ti diresti se fossi il tuo migliore amico? Dillo a te stesso adesso.",
        "Cosa puoi lasciare andare oggi che non ti serve piu?",
        "Il cambiamento e lento, come una farfalla nel bozzolo. Abbi pazienza con te stesso.",
        "Oggi fai una cosa con piena attenzione, anche solo bere un caffe.",
    ],
    PROFILE_CHILD: [
        "Fai 3 respiri profondi come un palloncino: gonfiati e sgonfiati lentamente! Bravo!",
        "Guarda intorno: riesci a trovare 3 cose di colore diverso? Elencale!",
        "Metti le mani sulla pancia e senti il respiro che sale e scende. Quante volte in 30 secondi?",
        "Pensa a una cosa che ti ha fatto sorridere ieri. Tienila in mente per un momento.",
        "Stai fermo 1 minuto e ascolta tutti i suoni intorno. Quanti ne senti?",
        "I pensieri brutti sono come nuvole: arrivano e se ne vanno. Tu sei il sole sotto.",
        "Disegna o scrivi una cosa bella di oggi, anche piccola piccola.",
        "Tendi i muscoli delle braccia forte forte, poi rilassali. Senti la differenza?",
        "Pensa a qualcuno che vuoi bene e mandalgli un pensiero gentile nel cuore.",
        "Oggi scegli una cosa da fare lentamente, come se fosse la prima volta.",
    ],
    PROFILE_NIGHT: [
        "Prima di dormire: inspira per 4 secondi, espira per 8. Aiuta il corpo a rilassarsi.",
        "Dopo il turno, nota 3 cose positive successe stanotte, anche piccole.",
        "Il tuo orologio biologico e diverso - ed e ok. Rispettalo senza sensi di colpa.",
        "Prima di andare a letto, abbassa le luci e allontanati dagli schermi per 20 minuti.",
        "Tendi e rilassa ogni gruppo muscolare partendo dai piedi. Il corpo ha lavorato duro.",
        "I pensieri sulla stanchezza sono solo pensieri. Osservali e lasciali passare.",
        "Cosa e andato bene stanotte? Anche una sola cosa conta.",
        "Prepara il tuo spazio notte: buio, fresco, silenzioso. Il riposo e produttivo.",
        "La stanchezza del turno notturno e reale. Merita rispetto e cura, non resistenza.",
        "Quando ti sveglierai, prenditi 5 minuti prima di guardare il telefono.",
    ],
}

_WAKE_DEFAULTS = {PROFILE_ADULT: 8,  PROFILE_CHILD: 7,  PROFILE_NIGHT: 16}
_EVE_DEFAULTS  = {PROFILE_ADULT: 21, PROFILE_CHILD: 19, PROFILE_NIGHT: 2}

# ---------------------------------------------------------------------------
# CSV helpers
# ---------------------------------------------------------------------------

_CSV_FIELDS = [
    "chat_id", "username", "subscribed_at",
    "profile", "morning_hour", "evening_hour",
    "onboarding_step", "recent_moods", "prompt_index",
]

_MOOD_FIELDS = ["timestamp", "chat_id", "username", "score", "trigger"]


def _ensure_csv(path: Path, fields: list[str]) -> None:
    if not path.exists():
        with path.open("w", newline="", encoding="utf-8") as fh:
            csv.DictWriter(fh, fieldnames=fields).writeheader()


def _load_subscribers() -> list[dict]:
    _ensure_csv(SUBSCRIBERS_CSV, _CSV_FIELDS)
    with SUBSCRIBERS_CSV.open("r", newline="", encoding="utf-8") as fh:
        return list(csv.DictReader(fh))


def _save_subscribers(rows: list[dict]) -> None:
    with SUBSCRIBERS_CSV.open("w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=_CSV_FIELDS)
        w.writeheader()
        w.writerows(rows)


def _get_sub(chat_id: int) -> Optional[dict]:
    for r in _load_subscribers():
        if r["chat_id"] == str(chat_id):
            return r
    return None


def _upsert(chat_id: int, **kwargs) -> dict:
    rows = _load_subscribers()
    for r in rows:
        if r["chat_id"] == str(chat_id):
            r.update({k: str(v) for k, v in kwargs.items()})
            _save_subscribers(rows)
            return r
    profile = kwargs.get("profile", PROFILE_ADULT)
    row: dict = {
        "chat_id": str(chat_id),
        "username": "",
        "subscribed_at": datetime.now().isoformat(timespec="seconds"),
        "profile": str(profile),
        "morning_hour": str(_WAKE_DEFAULTS.get(str(profile), 8)),
        "evening_hour": str(_EVE_DEFAULTS.get(str(profile), 21)),
        "onboarding_step": "1",
        "recent_moods": "",
        "prompt_index": "0",
    }
    row.update({k: str(v) for k, v in kwargs.items()})
    rows.append(row)
    _save_subscribers(rows)
    return row


def _remove_sub(chat_id: int) -> None:
    rows = [r for r in _load_subscribers() if r["chat_id"] != str(chat_id)]
    _save_subscribers(rows)
    logger.info("Removed chat_id=%s", chat_id)


def _log_mood(chat_id: int, username: str, score: int, trigger: str) -> None:
    _ensure_csv(MOOD_LOG_CSV, _MOOD_FIELDS)
    with MOOD_LOG_CSV.open("a", newline="", encoding="utf-8") as fh:
        csv.writer(fh).writerow([
            datetime.now().isoformat(timespec="seconds"),
            str(chat_id), username or "", str(score), trigger,
        ])
    sub = _get_sub(chat_id)
    if sub:
        moods = [int(x) for x in sub["recent_moods"].split(",") if x.strip().isdigit()]
        moods = (moods + [score])[-5:]
        _upsert(chat_id, recent_moods=",".join(str(m) for m in moods))
    logger.info("Mood chat_id=%s score=%s trigger=%s", chat_id, score, trigger)


def _next_prompt(chat_id: int, profile: str) -> str:
    sub = _get_sub(chat_id)
    idx = int(sub.get("prompt_index", "0")) if sub else 0
    library = PROMPTS.get(profile, PROMPTS[PROFILE_ADULT])
    _upsert(chat_id, prompt_index=str(idx + 1))
    return library[idx % len(library)]


def _low_mood_streak(sub: dict) -> bool:
    moods = [int(x) for x in sub.get("recent_moods", "").split(",") if x.strip().isdigit()]
    return len(moods) >= 3 and all(m <= 2 for m in moods[-3:])


# ---------------------------------------------------------------------------
# Text helpers
# ---------------------------------------------------------------------------

def _welcome(profile: str, wake: int) -> str:
    if profile == PROFILE_CHILD:
        return (
            f"Ciao! Sono Mindful Bot, il tuo amico della calma!\n\n"
            f"Ogni mattina alle {wake}:00 ti mando un esercizio divertente.\n"
            f"La sera ti chiedo com e andata la giornata.\n\n"
            f"Usa /stop quando vuoi fermarti. /aiuto per i comandi."
        )
    if profile == PROFILE_NIGHT:
        return (
            f"Benvenuto su Mindful Bot - versione turno notturno!\n\n"
            f"Il tuo orario e diverso dagli altri, ed e ok.\n"
            f"Riceverai un promemoria alle {wake}:00 e un check-in a fine turno.\n\n"
            f"Usa /stop per fermarti. /aiuto per i comandi."
        )
    return (
        f"Benvenuto su Mindful Bot!\n\n"
        f"Ogni mattina alle {wake}:00 un esercizio di mindfulness.\n"
        f"La sera un check sull umore.\n\n"
        f"Usa /stop per cancellarti. /aiuto per i comandi."
    )


def _mood_response(score: int, profile: str) -> str:
    if profile == PROFILE_CHILD:
        return {
            1: "Mi dispiace. Parla con qualcuno di cui ti fidi, ok?",
            2: "Capito. Anche le giornate grigie passano. Un abbraccio!",
            3: "Cosi cosi - va bene anche questo!",
            4: "Bene! Stai andando alla grande!",
            5: "FANTASTICO! Che bello sentirti cosi!",
        }.get(score, "Grazie!")
    return {
        1: "Mi dispiace. Ogni giorno e diverso. Respira.",
        2: "Capito. Prenditi cura di te oggi.",
        3: "Cosi cosi - va bene anche questo.",
        4: "Bene! Continua cosi.",
        5: "Fantastico! Porta questa energia con te.",
    }.get(score, "Grazie.")


def _support_note(profile: str) -> str:
    if profile == PROFILE_CHILD:
        return (
            "\n\nHo notato che hai avuto qualche giornata difficile. "
            "Parla con un adulto di cui ti fidi: genitori, insegnante o psicologo."
        )
    return (
        "\n\nHo notato che le ultime giornate sono state difficili. "
        "Potresti considerare di parlarne con il tuo psicologo o una persona di fiducia."
    )


# ---------------------------------------------------------------------------
# Onboarding conversation
# ---------------------------------------------------------------------------

async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    chat_id  = update.effective_chat.id
    user     = update.effective_user
    username = user.username or user.first_name or ""

    existing = _get_sub(chat_id)
    if existing and existing.get("onboarding_step", "0") == "0":
        profile = existing.get("profile", PROFILE_ADULT)
        await update.message.reply_text(
            f"Sei gia iscritto ({_PROFILE_LABELS.get(profile, profile)}).\n"
            "Usa /stop per cancellarti o /aiuto per i comandi.",
            reply_markup=ReplyKeyboardRemove(),
        )
        return ConversationHandler.END

    _upsert(chat_id, username=username, onboarding_step="1")
    keyboard = ReplyKeyboardMarkup(
        [["Per me (adulto)", "Per un bambino", "Lavoro di notte"]],
        one_time_keyboard=True,
        resize_keyboard=True,
    )
    await update.message.reply_text(
        "Benvenuto! Una domanda rapida per personalizzare i promemoria.\n\n"
        "Chi usera questo bot?",
        reply_markup=keyboard,
    )
    return ASK_PROFILE


async def handle_profile_choice(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    text    = update.message.text.strip().lower()
    chat_id = update.effective_chat.id

    if "bambino" in text:
        profile, default_hour, hint = PROFILE_CHILD, 7, "I bambini si svegliano spesso verso le 7:00."
    elif "notte" in text:
        profile, default_hour, hint = PROFILE_NIGHT, 16, "Chi lavora di notte spesso si sveglia nel pomeriggio (es. 16)."
    else:
        profile, default_hour, hint = PROFILE_ADULT, 8, "La maggior parte delle persone si sveglia tra le 7 e le 9."

    context.user_data["pending_profile"] = profile
    _upsert(chat_id, profile=profile, onboarding_step="2")

    await update.message.reply_text(
        f"Perfetto - profilo: {_PROFILE_LABELS[profile]}.\n\n"
        f"A che ora ti svegli (o finisci il turno)?\n"
        f"{hint}\n\n"
        f"Scrivi solo il numero dell ora (es. {default_hour}):",
        reply_markup=ReplyKeyboardRemove(),
    )
    return ASK_WAKE_HOUR


async def handle_wake_hour(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    text    = update.message.text.strip()
    chat_id = update.effective_chat.id

    try:
        hour = int(text)
        if not 0 <= hour <= 23:
            raise ValueError
    except ValueError:
        await update.message.reply_text("Scrivi un numero tra 0 e 23 (es. 8, 16):")
        return ASK_WAKE_HOUR

    profile      = context.user_data.get("pending_profile", PROFILE_ADULT)
    evening_hour = min(hour + 13, 23)
    _upsert(chat_id, morning_hour=str(hour), evening_hour=str(evening_hour), onboarding_step="0")

    await update.message.reply_text(_welcome(profile, hour), reply_markup=ReplyKeyboardRemove())
    logger.info("Onboarding complete chat_id=%s profile=%s wake=%s", chat_id, profile, hour)
    return ConversationHandler.END


async def cmd_stop(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    chat_id = update.effective_chat.id
    if _get_sub(chat_id):
        _remove_sub(chat_id)
        await update.message.reply_text("Iscrizione cancellata. Torna quando vuoi con /start.")
    else:
        await update.message.reply_text("Non risulti iscritto. Usa /start per iscriverti.")


async def cmd_help(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    chat_id = update.effective_chat.id
    sub     = _get_sub(chat_id)
    profile = sub.get("profile", PROFILE_ADULT) if sub else PROFILE_ADULT
    wake    = sub.get("morning_hour", "8")       if sub else "8"
    eve     = sub.get("evening_hour", "21")      if sub else "21"
    label   = _PROFILE_LABELS.get(profile, profile)
    await update.message.reply_text(
        f"Comandi:\n\n"
        f"/start  - Iscriviti (o ripeti onboarding)\n"
        f"/stop   - Cancella iscrizione\n"
        f"/umore  - Registra umore manuale (1-5)\n"
        f"/aiuto  - Questo messaggio\n\n"
        f"Profilo attivo: {label}\n"
        f"Promemoria mattutino: {wake}:00\n"
        f"Check serale: {eve}:00"
    )


async def cmd_mood(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    context.user_data["awaiting_mood"] = "manual"
    sub     = _get_sub(update.effective_chat.id)
    profile = sub.get("profile", PROFILE_ADULT) if sub else PROFILE_ADULT
    if profile == PROFILE_CHILD:
        await update.message.reply_text(
            "Come stai oggi?\n1 = Male  2 = Non bene  3 = Cosi cosi  4 = Bene  5 = Benissimo!"
        )
    else:
        await update.message.reply_text("Come stai? Rispondi con un numero da 1 (male) a 5 (benissimo).")


async def handle_mood_reply(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not context.user_data.get("awaiting_mood"):
        return
    text     = update.message.text.strip()
    chat_id  = update.effective_chat.id
    user     = update.effective_user
    username = user.username or user.first_name or ""
    trigger  = context.user_data["awaiting_mood"]

    if text not in {"1", "2", "3", "4", "5"}:
        await update.message.reply_text("Per favore rispondi con un numero da 1 a 5:")
        return

    score = int(text)
    _log_mood(chat_id, username, score, trigger)
    context.user_data.pop("awaiting_mood", None)

    sub     = _get_sub(chat_id)
    profile = sub.get("profile", PROFILE_ADULT) if sub else PROFILE_ADULT
    reply   = _mood_response(score, profile)
    if sub and _low_mood_streak(sub):
        reply += _support_note(profile)
    await update.message.reply_text(reply)


# ---------------------------------------------------------------------------
# Scheduled tick — runs every 30 min, sends to each user at their own hour
# ---------------------------------------------------------------------------

async def _safe_send(bot, chat_id: int, text: str) -> bool:
    try:
        await bot.send_message(chat_id=int(chat_id), text=text)
        return True
    except Forbidden:
        _remove_sub(int(chat_id))
        return False
    except NetworkError as exc:
        logger.error("Network error chat_id=%s: %s", chat_id, exc)
        return False


async def job_tick(bot, app: Application) -> None:
    now   = datetime.now()
    hour  = now.hour
    slot  = "morning" if now.minute < 30 else "evening"

    for sub in _load_subscribers():
        if sub.get("onboarding_step", "0") != "0":
            continue

        chat_id = int(sub["chat_id"])
        profile = sub.get("profile", PROFILE_ADULT)
        m_hour  = int(sub.get("morning_hour", _WAKE_DEFAULTS.get(profile, 8)))
        e_hour  = int(sub.get("evening_hour", _EVE_DEFAULTS.get(profile, 21)))

        if slot == "morning" and hour == m_hour:
            prompt = _next_prompt(chat_id, profile)
            prefix = "Buon risveglio!\n\n" if profile == PROFILE_NIGHT else "Buongiorno!\n\n"
            await _safe_send(bot, chat_id, prefix + prompt)

        elif slot == "evening" and hour == e_hour:
            pending: set = app.bot_data.setdefault("scheduled_mood_pending", set())
            msgs = {
                PROFILE_CHILD: "Com e andata la giornata? Rispondi con un numero da 1 a 5!",
                PROFILE_NIGHT: "Com e andato il turno? Da 1 (male) a 5 (benissimo).",
                PROFILE_ADULT: "Buonasera. Come ti senti stasera? Da 1 a 5.",
            }
            sent = await _safe_send(bot, chat_id, msgs.get(profile, msgs[PROFILE_ADULT]))
            if sent:
                pending.add(chat_id)


async def handle_scheduled_mood_reply(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    chat_id = update.effective_chat.id
    pending: set = context.bot_data.get("scheduled_mood_pending", set())
    if chat_id not in pending:
        return

    text     = update.message.text.strip()
    user     = update.effective_user
    username = user.username or user.first_name or ""

    if text not in {"1", "2", "3", "4", "5"}:
        await update.message.reply_text("Per favore rispondi con un numero da 1 a 5:")
        return

    score = int(text)
    _log_mood(chat_id, username, score, "scheduled")
    pending.discard(chat_id)

    sub     = _get_sub(chat_id)
    profile = sub.get("profile", PROFILE_ADULT) if sub else PROFILE_ADULT
    reply   = _mood_response(score, profile)
    if sub and _low_mood_streak(sub):
        reply += _support_note(profile)
    await update.message.reply_text(reply)


# ---------------------------------------------------------------------------
# Application & scheduler
# ---------------------------------------------------------------------------

def build_application(token: str) -> Application:
    app = Application.builder().token(token).build()

    onboarding = ConversationHandler(
        entry_points=[CommandHandler("start", cmd_start)],
        states={
            ASK_PROFILE:   [MessageHandler(filters.TEXT & ~filters.COMMAND, handle_profile_choice)],
            ASK_WAKE_HOUR: [MessageHandler(filters.TEXT & ~filters.COMMAND, handle_wake_hour)],
        },
        fallbacks=[CommandHandler("stop", cmd_stop)],
        allow_reentry=True,
    )

    app.add_handler(onboarding)
    app.add_handler(CommandHandler("stop",  cmd_stop))
    app.add_handler(CommandHandler("help",  cmd_help))
    app.add_handler(CommandHandler("aiuto", cmd_help))
    app.add_handler(CommandHandler("umore", cmd_mood))
    app.add_handler(CommandHandler("mood",  cmd_mood))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_mood_reply))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_scheduled_mood_reply))

    return app


def build_scheduler(app: Application) -> AsyncIOScheduler:
    scheduler = AsyncIOScheduler(timezone="Europe/Rome")
    scheduler.add_job(
        job_tick,
        trigger=IntervalTrigger(minutes=30, timezone="Europe/Rome"),
        args=[app.bot, app],
        id="tick",
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
        raise RuntimeError("TELEGRAM_BOT_TOKEN not set. Copy .env.example to .env and fill it in.")

    app       = build_application(token)
    scheduler = build_scheduler(app)
    loop      = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)

    async def _run() -> None:
        scheduler.start()
        logger.info("Scheduler started (30-min tick, Europe/Rome)")
        async with app:
            await app.initialize()
            await app.start()
            logger.info("Mindful Bot running. Ctrl+C to stop.")
            await app.updater.start_polling(drop_pending_updates=True)

            stop_event = asyncio.Event()

            def _shutdown(signum, frame):
                logger.info("Signal %s - shutting down", signum)
                loop.call_soon_threadsafe(stop_event.set)

            signal.signal(signal.SIGINT,  _shutdown)
            signal.signal(signal.SIGTERM, _shutdown)

            await stop_event.wait()
            await app.updater.stop()
            await app.stop()
            scheduler.shutdown(wait=False)
            logger.info("Mindful Bot stopped cleanly.")

    loop.run_until_complete(_run())


if __name__ == "__main__":
    main()
