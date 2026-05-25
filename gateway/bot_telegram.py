"""
gateway/bot_telegram.py — Carlos (Bot/Integration Engineer)

Telegram bot: users send a plain-text message, it's submitted to the
6-agent pipeline via PipelineAdapter, result is sent back as a reply.

Setup:
  export TELEGRAM_BOT_TOKEN=...   # from @BotFather
  python -m gateway.bot_telegram

Commands:
  /start  — welcome message
  Any text — submitted to pipeline
"""

import logging
import os
import re
from pathlib import Path

from config.brand import b, fmt

# Load .env from repo root so TELEGRAM_BOT_TOKEN is available without manual export
_env_file = Path(__file__).resolve().parent.parent / ".env"
if _env_file.exists():
    for _line in _env_file.read_text(encoding="utf-8").splitlines():
        _line = _line.strip()
        if _line and not _line.startswith("#") and "=" in _line:
            _k, _, _v = _line.partition("=")
            os.environ.setdefault(_k.strip(), _v.strip())

from telegram import Update
from telegram.constants import ChatAction
from telegram.ext import Application, CommandHandler, ContextTypes, MessageHandler, filters

from gateway.pipeline_adapter import PipelineAdapter

logging.basicConfig(
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)

_adapter = PipelineAdapter()

# Strip Telegram markdown formatting before sending to pipeline
_MARKDOWN_RE = re.compile(r"[*_`\[\]()~>#+=|{}.!\\-]")


def _normalize(text: str) -> str:
    clean = _MARKDOWN_RE.sub(" ", text)
    return " ".join(clean.split()).strip()


async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text(
        fmt(b("ui_strings.telegram_welcome")) + "\n\n"
        "Examples:\n"
        "• I need a landing page for my restaurant\n"
        "• Create an invoice PDF for 500€\n"
        "• Build a chatbot for my website\n\n"
        "Just type your request and I'll take care of the rest."
    )


async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    raw_text = update.message.text or ""
    user = update.effective_user
    chat_id = update.effective_chat.id

    await update.message.chat.send_action(ChatAction.TYPING)

    normalized = _normalize(raw_text)
    if not normalized:
        await update.message.reply_text("Please send a text message describing what you need.")
        return

    logger.info(
        "Telegram request | user_id=%s chat_id=%s text_length=%d",
        user.id, chat_id, len(normalized),
    )

    result = _adapter.submit(
        text=normalized,
        channel="telegram",
        metadata={"user_id": user.id, "chat_id": chat_id},
    )

    if result["status"] == "error":
        await update.message.reply_text(
            "We can't process that yet — Luigi needs to approve this type of request. "
            "Please try a different request."
        )
        return

    await update.message.reply_text(
        f"Got it! Your request is being processed.\n\n"
        f"Job ID: `{result['job_id']}`\n\n"
        "You'll receive the result here when it's ready.",
        parse_mode="Markdown",
    )


def main() -> None:
    token = os.environ["TELEGRAM_BOT_TOKEN"]
    app = Application.builder().token(token).build()
    app.add_handler(CommandHandler("start", cmd_start))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    logger.info("[bot_telegram] Polling for updates...")
    app.run_polling()


if __name__ == "__main__":
    main()
