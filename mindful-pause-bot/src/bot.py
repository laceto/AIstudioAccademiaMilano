import asyncio
import logging
from telegram import Update
from telegram.ext import (
    Application,
    CommandHandler,
    ConversationHandler,
    MessageHandler,
    filters,
    ContextTypes,
)
from .chains import pause_chain, options_chain, reflection_chain, close_chain
from .storage import init_db, log_session

logger = logging.getLogger(__name__)

AWAITING_TRIGGER, CHOICE, REFLECTING = range(3)

WELCOME = (
    "👋 I'm your pause coach.\n\n"
    "When you feel reactive — about to say something you'll regret, "
    "stuck in the same loop, running on autopilot — come here first.\n\n"
    "Just describe what's happening, or type /pause to begin."
)


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text(WELCOME)


async def pause_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    await update.message.reply_text("What's happening? Describe the situation.")
    return AWAITING_TRIGGER


async def run_pause_flow(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    trigger = update.message.text.strip()
    if not trigger:
        return ConversationHandler.END

    context.user_data["trigger"] = trigger

    try:
        await update.message.reply_text("⏸ Stopping autopilot...")

        pause_response = await pause_chain.ainvoke({"trigger": trigger})
        await update.message.reply_text(pause_response.content)

        await asyncio.sleep(0.8)

        options_response = await options_chain.ainvoke({"trigger": trigger})
        await update.message.reply_text(options_response.content, parse_mode="Markdown")

    except Exception:
        logger.exception("Error in pause flow")
        await update.message.reply_text(
            "Something went wrong on my end. Try again in a moment."
        )
        return ConversationHandler.END

    return CHOICE


async def receive_choice(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    choice = update.message.text.strip()
    trigger = context.user_data.get("trigger", "")
    context.user_data["choice"] = choice

    try:
        response = await reflection_chain.ainvoke({"choice": choice, "trigger": trigger})
        await update.message.reply_text(response.content)
    except Exception:
        logger.exception("Error generating reflection prompt")
        await update.message.reply_text("Got it. How does that choice feel to you?")

    return REFLECTING


async def receive_reflection(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    reflection = update.message.text.strip()
    trigger = context.user_data.get("trigger", "")
    choice = context.user_data.get("choice", "")

    try:
        response = await close_chain.ainvoke(
            {"trigger": trigger, "choice": choice, "reflection": reflection}
        )
        await update.message.reply_text(response.content)

        log_session(
            user_id=str(update.effective_user.id),
            trigger=trigger,
            choice=choice,
            reflection=reflection,
        )
    except Exception:
        logger.exception("Error closing session")
        await update.message.reply_text("Great work. Session saved. 🌱")

    context.user_data.clear()
    return ConversationHandler.END


async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    context.user_data.clear()
    await update.message.reply_text("Paused. Come back when ready. 🌱")
    return ConversationHandler.END


def build_application(token: str) -> Application:
    init_db()

    app = Application.builder().token(token).build()

    app.add_handler(CommandHandler("start", start))

    conv_handler = ConversationHandler(
        entry_points=[
            CommandHandler("pause", pause_command),
            MessageHandler(filters.TEXT & ~filters.COMMAND, run_pause_flow),
        ],
        states={
            AWAITING_TRIGGER: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, run_pause_flow),
            ],
            CHOICE: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, receive_choice),
            ],
            REFLECTING: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, receive_reflection),
            ],
        },
        fallbacks=[CommandHandler("cancel", cancel)],
        allow_reentry=True,
    )

    app.add_handler(conv_handler)
    return app
