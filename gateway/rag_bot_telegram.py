"""
gateway/rag_bot_telegram.py — RAG knowledge-base Telegram bot

Dedicated bot for querying the AI Studio repo knowledge base.
Every message is answered by the RAG pipeline — no production pipeline.

Setup:
  export RAG_BOT_TOKEN=...      # from @BotFather (/newbot)
  export RAG_API_URL=http://localhost:8000   # or deployed RAG service
  python -m gateway.rag_bot_telegram

Commands:
  /start  — welcome + usage
  /ask    — alias for plain text (shows in command menu)
  Any text — answered by RAG
"""

import logging
import os
from pathlib import Path

import httpx
from telegram import Update
from telegram.constants import ChatAction
from telegram.ext import Application, CommandHandler, ContextTypes, MessageHandler, filters

from config.brand import b, fmt

# Load .env from repo root
_env_file = Path(__file__).resolve().parent.parent / ".env"
if _env_file.exists():
    for _line in _env_file.read_text(encoding="utf-8").splitlines():
        _line = _line.strip()
        if _line and not _line.startswith("#") and "=" in _line:
            _k, _, _v = _line.partition("=")
            os.environ.setdefault(_k.strip(), _v.strip())

logging.basicConfig(
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)


async def _rag_answer(query: str) -> str:
    rag_url = os.environ.get("RAG_API_URL", "").rstrip("/")
    if not rag_url:
        return "RAG_API_URL not configured — knowledge base unavailable."
    try:
        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.post(f"{rag_url}/chat/sync", json={"query": query})
            return resp.json().get("answer", "No answer returned.")
    except Exception as exc:
        logger.error("RAG call failed: %s", exc)
        return f"RAG error: {exc}"


async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text(
        "Ciao! Sono l'assistente knowledge base di " + b("studio.name") + ".\n\n"
        "Posso rispondere a domande sul repo, gli agenti, i prezzi e i processi dello studio.\n\n"
        "Esempi:\n"
        "• Come funziona la pipeline a 6 agenti?\n"
        "• Come prezza Marco i prodotti sconosciuti?\n"
        "• Quali issue sono aperte?\n"
        "• Cosa fa Chiara?\n\n"
        "Scrivi qualsiasi domanda."
    )


async def cmd_ask(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = " ".join(context.args).strip() if context.args else ""
    if not query:
        await update.message.reply_text("Uso: /ask <domanda>")
        return
    await update.message.chat.send_action(ChatAction.TYPING)
    logger.info("RAG /ask | user_id=%s query=%r", update.effective_user.id, query[:80])
    answer = await _rag_answer(query)
    await update.message.reply_text(answer)


async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = (update.message.text or "").strip()
    if not query:
        return
    await update.message.chat.send_action(ChatAction.TYPING)
    logger.info("RAG query | user_id=%s query=%r", update.effective_user.id, query[:80])
    answer = await _rag_answer(query)
    await update.message.reply_text(answer)


def main() -> None:
    token = os.environ.get("TELEGRAM_RAG_BOT_TOKEN", "")
    if not token:
        raise RuntimeError("TELEGRAM_RAG_BOT_TOKEN not set — create a bot via @BotFather and add it to .env")
    app = Application.builder().token(token).build()
    app.add_handler(CommandHandler("start", cmd_start))
    app.add_handler(CommandHandler("ask", cmd_ask))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    logger.info("[rag_bot_telegram] Polling for updates...")
    app.run_polling()


if __name__ == "__main__":
    main()
