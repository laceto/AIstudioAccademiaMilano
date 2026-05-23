"""
bot_telegram.py — Telegram bot: parse message, create event in all calendars.

Setup:
    export TELEGRAM_BOT_TOKEN=your_token  # from @BotFather
    export OPENAI_API_KEY=sk-...
    python bot_telegram.py

Send: "Pranzo con Marco domani alle 13 a Milano"
"""

import logging, os
from telegram import Update
from telegram.ext import Application, MessageHandler, filters, ContextTypes
from event_parser import extract_event
from calendar_sync import sync_to_all_calendars

logging.basicConfig(level=logging.INFO)


async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text("🔄 Parsing event...")
    try:
        event = extract_event(update.message.text)
    except Exception as e:
        await update.message.reply_text(f"❌ Could not parse: {e}"); return
    results = sync_to_all_calendars(event)
    lines = [f"📅 *{event.title}*", f"`{event.date}` `{event.start_time}`–`{event.end_time}`"]
    if event.location: lines.append(f"📍 {event.location}")
    lines.append("")
    for r in results:
        lines.append(f"✅ {r.provider}" + (f" — [open]({r.link})" if r.link else "") if r.status == "ok"
                     else f"⏭️ {r.provider} (not configured)" if r.status == "skipped"
                     else f"❌ {r.provider}: {r.error}")
    await update.message.reply_text("\n".join(lines), parse_mode="Markdown", disable_web_page_preview=True)


def main():
    app = Application.builder().token(os.environ["TELEGRAM_BOT_TOKEN"]).build()
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    print("[bot_telegram] Running. Send a message in Telegram.")
    app.run_polling()


if __name__ == "__main__":
    main()
