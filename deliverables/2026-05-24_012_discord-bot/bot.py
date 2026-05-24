"""
AI Studio Discord Bot — entry point.

Handles:
  - AI chat: reply when mentioned or in DMs (Claude claude-sonnet-4-6)
  - Slash commands: /ask /weather /latest /help  (registered in commands.py)
  - Ready event: logs connected guilds

Run:
    python bot.py

Required env vars:
    DISCORD_BOT_TOKEN
    ANTHROPIC_API_KEY     (for /ask and @mention chat)
    OPENWEATHERMAP_API_KEY  (for /weather)
"""

import os
import discord
from discord.ext import commands
from commands import setup_commands
from ai_chat import reply

TOKEN = os.environ.get("DISCORD_BOT_TOKEN")

intents = discord.Intents.default()
intents.message_content = True

bot = commands.Bot(command_prefix="!", intents=intents)


@bot.event
async def on_ready():
    guilds = [g.name for g in bot.guilds]
    print(f"[bot] Logged in as {bot.user} | Guilds: {guilds}")
    try:
        synced = await bot.tree.sync()
        print(f"[bot] Synced {len(synced)} slash commands")
    except Exception as e:
        print(f"[bot] Sync failed: {e}")


@bot.event
async def on_message(message: discord.Message):
    if message.author.bot:
        return

    is_dm = isinstance(message.channel, discord.DMChannel)
    is_mention = bot.user in message.mentions

    if is_dm or is_mention:
        text = message.content.replace(f"<@{bot.user.id}>", "").strip()
        if not text:
            await message.reply("Ciao! Ask me anything about AI Studio. 👋")
            return
        async with message.channel.typing():
            response = await reply(text)
        await message.reply(response)
        return

    await bot.process_commands(message)


if __name__ == "__main__":
    if not TOKEN:
        raise RuntimeError(
            "DISCORD_BOT_TOKEN not set. "
            "Get it from discord.com/developers/applications → Bot → Reset Token"
        )
    setup_commands(bot)
    bot.run(TOKEN)
