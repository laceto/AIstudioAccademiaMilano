"""
bot_telegram.py — Telegram bot: receive a message, create event in all calendars.

Setup:
    1. Create a bot with @BotFather on Telegram → get TELEGRAM_BOT_TOKEN
    2. Set env vars for calendar providers (see calendar_sync.py)
    3. Run: python bot_telegram.py

Usage in Telegram:
    “Pranzo con Marco domani alle 13 in Via Torino 5, Milano”
    “Board meeting Friday 9-11am via Zoom https://zoom.us/j/123”
    “Call with London team next Tuesday at 3pm for 45min”
"""

import logging
import os

from telegram import Update
from telegram.ext import Application, MessageHandler, filters, ContextTypes

from event_parser import extract_event
from calendar_sync import sync_to_all_calendars

logging.basicConfig(level=logging.INFO)


async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    text = update.message.text
    await update.message.reply_text("🔄 Parsing event...")

    try:
        event = extract_event(text)
    except Exception as e:
        await update.message.reply_text(f"❌ Could not parse event: {e}")
        return

    results = sync_to_all_calendars(event)

    lines = [f"📅 *{event.title}*", f"`{event.date}` at `{event.start_time}` → `{event.end_time}`"]
    if event.location:
        lines.append(f"📍 {event.location}")
    lines.append("")

    for r in results:
        if r.status == "ok":
            link = f" — [open]({r.link})" if r.link else ""
            lines.append(f"✅ {r.provider}{link}")
        elif r.status == "skipped":
            lines.append(f"⏭️ {r.provider} (not configured)")
        else:
            lines.append(f"❌ {r.provider}: {r.error}")

    await update.message.reply_text(
        "\n".join(lines),
        parse_mode="Markdown",
        disable_web_page_preview=True,
    )


def main() -> None:
    token = os.environ["TELEGRAM_BOT_TOKEN"]
    app = Application.builder().token(token).build()
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    print("[bot_telegram] Running. Send a message in Telegram.")
    app.run_polling()


if __name__ == "__main__":
    main()
