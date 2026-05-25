"""
AI Studio Master Bot — Unified Telegram bot.
Combines Mindful Bot (D017) and SOAP Note Generator (D018) in one codebase.

Modes:
  - Mindfulness: /start, /stop, /mood + scheduled 8AM/8PM jobs
  - SOAP notes:  /soap — conversational flow, generates SOAP note via OpenAI, sends PDF

Usage:
    python bot.py

Environment:
    TELEGRAM_BOT_TOKEN — required
    OPENAI_API_KEY     — required for /soap; mindfulness works without it
"""

from __future__ import annotations

import asyncio
import csv
import io
import json
import logging
import os
import signal
from datetime import date, datetime
from pathlib import Path

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from dotenv import load_dotenv
from fpdf import FPDF
from openai import OpenAI
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
logger = logging.getLogger("aistudio_master_bot")

_api_key = os.environ.get("OPENAI_API_KEY", "")
_openai = OpenAI(api_key=_api_key) if _api_key else None

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
    "Respira. Inspira per 4 secondi, trattieni per 4, espira per 6. Ripeti 3 volte. Sei nel momento presente.",
    "Oggi nota una cosa bella che di solito ignori. Un suono, un colore, una sensazione.",
    "Cosa provi adesso nel corpo? Scansiona dalla testa ai piedi, senza giudizio.",
    "Nomina 3 cose per cui sei grato oggi, anche piccole.",
    "Fai una pausa di 60 secondi. Nessun telefono, nessun pensiero. Solo respiro.",
    "I tuoi pensieri sono come onde — arrivano e passano. Osservali senza aggrapparti.",
    "Accendi un momento di gentilezza verso te stesso. Cosa ti diresti se fossi il tuo migliore amico?",
    "Cosa puoi lasciare andare oggi che non ti serve piu?",
    "Il cambiamento e lento e invisibile, come una farfalla nel bozzolo. Abbi pazienza con te stesso.",
    "Oggi fai una cosa con piena attenzione — anche solo lavare i piatti o bere un caffe.",
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
# SOAP generation (pure functions — no Streamlit dependencies)
# ---------------------------------------------------------------------------

_SOAP_SYSTEM = (
    "Sei un assistente clinico per psicologi italiani.\n"
    "Ricevi un riassunto libero di una sessione terapeutica e lo trasformi in una nota\n"
    "strutturata formato SOAP (Soggettivo, Obiettivo, Valutazione, Piano).\n\n"
    "Regole:\n"
    "- Usa la terza persona per il paziente (Il paziente riferisce...)\n"
    "- Mantieni linguaggio clinico ma leggibile\n"
    "- Non aggiungere diagnosi che non siano gia presenti nel riassunto\n"
    "- Ogni sezione: 2-5 frasi concise\n"
    "- Lingua: italiano professionale\n\n"
    "Rispondi ESCLUSIVAMENTE con un oggetto JSON valido nel formato:\n"
    '{"soggettivo": "...", "oggettivo": "...", "assessment": "...", "piano": "..."}\n'
    "Nessun testo aggiuntivo fuori dal JSON."
)

_SOAP_DISCLAIMER = (
    "NOTA PROFESSIONALE: questo documento e una bozza generata da un sistema AI "
    "e non sostituisce il giudizio clinico del professionista. "
    "Revisione obbligatoria prima di qualsiasi utilizzo clinico."
)


def generate_soap(
    notes: str,
    patient_code: str,
    session_num: str,
    approach: str,
) -> dict[str, str]:
    """
    Call OpenAI and return a SOAP dict with keys:
    soggettivo, oggettivo, assessment, piano.

    Uses the module-level _openai client.
    Raises ValueError if _openai is None or parsing fails.
    """
    if _openai is None:
        raise ValueError("OPENAI_API_KEY non configurata.")

    user_prompt = (
        f"Codice paziente: {patient_code or 'N/D'}\n"
        f"Sessione n. {session_num or 'N/D'}\n"
        f"Approccio terapeutico: {approach or 'N/D'}\n\n"
        f"Note della seduta:\n{notes}\n\n"
        "Genera la nota SOAP completa nel formato JSON richiesto."
    )

    response = _openai.chat.completions.create(
        model="gpt-4o-mini",
        messages=[
            {"role": "system", "content": _SOAP_SYSTEM},
            {"role": "user", "content": user_prompt},
        ],
        max_tokens=800,
        temperature=0.3,
    )

    raw = response.choices[0].message.content.strip()

    # Strip markdown code fences if present
    if raw.startswith("```"):
        lines = raw.splitlines()
        raw = "\n".join(lines[1:-1] if lines[-1].strip() == "```" else lines[1:])

    try:
        soap = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise ValueError(f"Risposta AI non valida (JSON parse error): {exc}") from exc

    required_keys = {"soggettivo", "oggettivo", "assessment", "piano"}
    missing = required_keys - soap.keys()
    if missing:
        raise ValueError(f"Campi SOAP mancanti nella risposta: {missing}")

    return soap


def create_soap_pdf(
    soap: dict[str, str],
    patient_code: str,
    approach: str,
) -> bytes:
    """
    Build a SOAP note PDF and return raw bytes.
    Uses fpdf2 with A4 format and UTF-8 compatible font (Helvetica).
    """
    pdf = FPDF(orientation="P", unit="mm", format="A4")
    pdf.set_auto_page_break(auto=True, margin=20)
    pdf.add_page()

    # Header
    pdf.set_font("Helvetica", "B", 16)
    pdf.cell(0, 10, "Nota SOAP - Bozza AI", ln=True, align="C")
    pdf.set_font("Helvetica", "", 10)
    pdf.cell(0, 6, f"Data: {date.today().isoformat()}", ln=True, align="C")
    if patient_code:
        pdf.cell(0, 6, f"Codice paziente: {patient_code}", ln=True, align="C")
    if approach and approach not in ("Non specificato", "N/D"):
        pdf.cell(0, 6, f"Approccio: {approach}", ln=True, align="C")
    pdf.ln(6)

    # Disclaimer box
    pdf.set_fill_color(255, 240, 240)
    pdf.set_font("Helvetica", "I", 9)
    pdf.multi_cell(0, 5, _SOAP_DISCLAIMER, fill=True, border=1)
    pdf.ln(6)

    # SOAP sections
    sections = [
        ("S - Soggettivo", soap.get("soggettivo", "")),
        ("O - Oggettivo", soap.get("oggettivo", "")),
        ("A - Assessment", soap.get("assessment", "")),
        ("P - Piano", soap.get("piano", "")),
    ]

    for title, content in sections:
        pdf.set_font("Helvetica", "B", 12)
        pdf.cell(0, 8, title, ln=True)
        pdf.set_font("Helvetica", "", 11)
        # Replace non-ASCII characters that Helvetica can't handle
        safe_content = content.encode("latin-1", errors="replace").decode("latin-1")
        pdf.multi_cell(0, 6, safe_content)
        pdf.ln(4)

    # Footer
    pdf.set_y(-20)
    pdf.set_font("Helvetica", "I", 8)
    pdf.cell(0, 5, "AI Studio Accademia Milano - Strumento di supporto clinico", align="C")

    return pdf.output()


# ---------------------------------------------------------------------------
# Command handlers — Mindfulness (from D017, copied as-is)
# ---------------------------------------------------------------------------


async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user = update.effective_user
    chat_id = update.effective_chat.id
    username = user.username or user.first_name or ""
    _subscribe(chat_id, username)
    await update.message.reply_text(
        "Benvenuto su AI Studio Master Bot!\n\n"
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
            "Hai cancellato l'iscrizione. Non riceverai piu i promemoria quotidiani.\n"
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
        "/mood — Registra manualmente il tuo umore (1-5)\n"
        "/soap — Genera una nota SOAP da note libere della seduta\n"
        "/annulla — Annulla l'operazione corrente\n"
        "/help — Mostra questo messaggio di aiuto\n\n"
        "Ogni giorno riceverai:\n"
        "* 08:00 — Un esercizio di mindfulness\n"
        "* 20:00 — Una domanda sul tuo umore serale"
    )


async def cmd_mood(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Initiate a manual mood check-in."""
    context.user_data["awaiting_mood"] = "manual"
    await update.message.reply_text(
        "Come stai oggi? Rispondi con un numero da 1 (male) a 5 (benissimo)"
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
            1: "Mi dispiace. Ricorda che ogni giorno e diverso. Respira.",
            2: "Capito. Prenditi cura di te oggi.",
            3: "Cosi cosi — va bene anche questo.",
            4: "Bene! Continua cosi.",
            5: "Fantastico! Porta questa energia con te.",
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
        await _safe_send(bot, row["chat_id"], f"Buongiorno!\n\n{prompt}")


async def job_evening_mood(bot, app: Application) -> None:
    """20:00 daily — send mood check-in to all subscribers."""
    subscribers = _load_subscribers()
    logger.info("Evening mood job: %d subscribers", len(subscribers))
    for row in subscribers:
        chat_id = int(row["chat_id"])
        sent = await _safe_send(
            bot,
            chat_id,
            "Buonasera Come ti senti stasera? Rispondi con un numero da 1 a 5.",
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
            1: "Mi dispiace. Ricorda che ogni giorno e diverso. Respira.",
            2: "Capito. Prenditi cura di te.",
            3: "Cosi cosi — va bene anche questo.",
            4: "Bene! Continua cosi.",
            5: "Fantastico! Porta questa energia con te.",
        }
        await update.message.reply_text(responses[score])
    else:
        await update.message.reply_text(
            "Per favore rispondi con un numero da 1 a 5:"
        )


# ---------------------------------------------------------------------------
# Command handlers — SOAP (D018)
# ---------------------------------------------------------------------------


async def cmd_soap(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not _openai:
        await update.message.reply_text(
            "OPENAI_API_KEY non configurata. Contatta l'amministratore."
        )
        return
    context.user_data["awaiting_soap_notes"] = True
    await update.message.reply_text(
        "*Generatore Note SOAP*\n\n"
        "Inviami le tue note libere della seduta.\n"
        "Scrivi tutto in un unico messaggio: cosa ha detto il paziente, "
        "le tue osservazioni, cosa hai pianificato.\n\n"
        "_Usa /annulla per annullare._",
        parse_mode="Markdown",
    )


async def cmd_annulla(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    context.user_data.pop("awaiting_soap_notes", None)
    context.user_data.pop("awaiting_mood", None)
    await update.message.reply_text("Operazione annullata.")


async def handle_soap_notes(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle free-text session notes for SOAP generation. Runs BEFORE handle_mood_reply."""
    if not context.user_data.get("awaiting_soap_notes"):
        return

    notes = update.message.text.strip()
    context.user_data.pop("awaiting_soap_notes", None)

    await update.message.reply_text("Analisi in corso...")

    try:
        soap = generate_soap(
            notes=notes,
            patient_code="",
            session_num="Non specificato",
            approach="Non specificato",
        )

        # Send structured text first
        text = (
            "*Nota SOAP - Bozza AI*\n\n"
            f"*S - Soggettivo*\n{soap['soggettivo']}\n\n"
            f"*O - Oggettivo*\n{soap['oggettivo']}\n\n"
            f"*A - Assessment*\n{soap['assessment']}\n\n"
            f"*P - Piano*\n{soap['piano']}\n\n"
            "Bozza AI - revisione clinica obbligatoria prima dell'uso."
        )
        await update.message.reply_text(text, parse_mode="Markdown")

        # Send PDF as document
        pdf_bytes = create_soap_pdf(soap, patient_code="", approach="Non specificato")
        filename = f"soap_{date.today().isoformat()}.pdf"
        await update.message.reply_document(
            document=io.BytesIO(pdf_bytes),
            filename=filename,
            caption="Scarica la nota SOAP in PDF.",
        )

    except ValueError as exc:
        await update.message.reply_text(f"Errore nella generazione. Riprova. ({exc})")
    except Exception as exc:
        await update.message.reply_text(f"Errore imprevisto: {exc}")


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
    app.add_handler(CommandHandler("soap", cmd_soap))
    app.add_handler(CommandHandler("annulla", cmd_annulla))

    # Text replies — order matters:
    # 1. SOAP notes handler (must come first)
    # 2. Manual mood reply
    # 3. Scheduled mood reply
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_soap_notes))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_mood_reply))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_scheduled_mood_reply))

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
            logger.info("AI Studio Master Bot is running. Press Ctrl+C to stop.")
            await app.updater.start_polling(drop_pending_updates=True)

            stop_event = asyncio.Event()

            def _shutdown(signum, frame):  # noqa: ANN001
                logger.info("Signal %s received — shutting down...", signum)
                loop.call_soon_threadsafe(stop_event.set)

            signal.signal(signal.SIGINT, _shutdown)
            signal.signal(signal.SIGTERM, _shutdown)

            await stop_event.wait()

            await app.updater.stop()
            await app.stop()
            scheduler.shutdown(wait=False)
            logger.info("AI Studio Master Bot stopped cleanly.")

    loop.run_until_complete(_run())


if __name__ == "__main__":
    main()
