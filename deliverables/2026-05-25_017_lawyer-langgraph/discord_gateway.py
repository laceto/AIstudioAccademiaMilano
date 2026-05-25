"""
Avvocato AI — Discord Gateway.

This is the answer to: "can we connect to PlayStation / Xbox?"

REALITY CHECK:
  - PlayStation Network has NO public developer API. Zero.
  - Xbox Live has a limited REST API (Microsoft Graph) for achievements,
    friends, presence — but no in-game message injection.
  - Nintendo Switch: same story, no public API.

THE BRIDGE THAT WORKS:
  Discord is the de-facto communication layer for gamers worldwide.
  - PS5 has a native Discord app (released 2023) — voice + messages.
  - Xbox has Discord integration built-in since 2022.
  - The Discord overlay on PC shows notifications WHILE you play.
  - Gamers always have Discord open on their phone, PC, or console.

  → Build a Discord bot that wraps the lawyer graph.
  → Michele's father sets up a Discord server for his clients.
  → Clients (even while on PS5 / Xbox) DM the bot or use #avvocato channel.
  → The bot pipes the message through the full LangGraph pipeline.
  → Legal response arrives as a Discord DM — client reads it between rounds.

SETUP:
  1. Go to https://discord.com/developers/applications → New Application
  2. Bot section → Add Bot → copy TOKEN
  3. OAuth2 → URL Generator → bot + Send Messages + Read Messages
  4. Invite the bot to your server
  5. Set env vars: DISCORD_BOT_TOKEN, ANTHROPIC_API_KEY
  6. Run: python discord_gateway.py

XBOX LIVE (bonus — presence/achievements only):
  Microsoft Azure → register app → request Xbox Live permission
  Scopes: XboxLive.signin, XboxLive.offline_access
  Use: show lawyer bot "Sei online su Xbox — ti mando il parere quando esci dalla partita"
"""
import asyncio
import logging
import os
import sys
from typing import Optional

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

try:
    import discord
    from discord.ext import commands
    DISCORD_AVAILABLE = True
except ImportError:
    DISCORD_AVAILABLE = False

from graph import run_case
from state import MATTER_TYPES

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
log = logging.getLogger("avvocato-discord")

# ── Bot configuration ─────────────────────────────────────────────────────────

CHANNEL_TRIGGER    = "avvocato"   # bot responds in any channel with this in the name
DM_ENABLED         = True         # bot also responds to DMs
MAX_DISCORD_CHARS  = 2000         # Discord message character limit
LAWYER_CHANNEL_ID  = None         # set to a specific channel int to restrict

WELCOME_MESSAGE = """⚖️ **Avvocato AI** — Studio Legale Intelligente

Sono il tuo assistente legale digitale. Descrivi il tuo problema e riceverai:
• Analisi della normativa italiana/europea applicabile
• Bozza di documento o parere legale
• Stima dei costi professionali

Scrivi la tua richiesta in questa chat — anche mentre sei in partita su PS5 o Xbox. 🎮

_Tutti i pareri sono informativi. Per assistenza legale vincolante, contatta direttamente l'Avvocato._
"""


# ── Xbox Live presence stub ───────────────────────────────────────────────────

class XboxPresence:
    """
    Minimal Xbox Live presence check via Microsoft Graph.
    Requires: Azure app registration with XboxLive.signin scope.
    Full docs: https://learn.microsoft.com/en-us/gaming/gdk/_content/gc/reference/live/rest/
    """

    def __init__(self, access_token: Optional[str] = None):
        self.token = access_token

    async def is_gaming(self, xbox_gamertag: str) -> tuple[bool, Optional[str]]:
        """
        Returns (is_currently_gaming, current_game_title).
        Stub: always returns False without a real token.
        """
        if not self.token:
            return False, None
        try:
            import aiohttp
            headers = {
                "Authorization": f"XBL3.0 x={self.token}",
                "x-xbl-contract-version": "3",
                "Accept": "application/json",
            }
            url = f"https://userpresence.xboxlive.com/users/gt({xbox_gamertag})/devices/current/titles/current"
            async with aiohttp.ClientSession() as s:
                async with s.get(url, headers=headers) as r:
                    if r.status == 200:
                        data = await r.json()
                        title = data.get("titles", [{}])[0].get("name")
                        return True, title
        except Exception as e:
            log.warning(f"Xbox Live check failed: {e}")
        return False, None


# ── Pipeline runner (async wrapper) ───────────────────────────────────────────

async def ask_avvocato(
    request: str,
    client_name: str,
    contact_method: str = "discord",
) -> tuple[str, dict]:
    """
    Runs the full LangGraph lawyer pipeline in a thread pool
    (langgraph.stream is sync; Discord is async).
    Returns (formatted_response, final_state).
    """
    loop = asyncio.get_event_loop()
    steps, final_state = await loop.run_in_executor(
        None,
        lambda: run_case(request, client_name, contact_method),
    )

    # Format the response for Discord
    draft   = final_state.get("draft_document", "")
    invoice = final_state.get("invoice", {})
    matter  = MATTER_TYPES.get(final_state.get("matter_type", "unknown"), "unknown")

    lines = []
    lines.append(f"⚖️ **Pratica elaborata — {matter}**")
    lines.append("")

    if draft:
        # Truncate for Discord's 2000-char limit
        preview = draft[:1400]
        if len(draft) > 1400:
            preview += "\n\n_[documento completo disponibile su richiesta]_"
        lines.append(preview)
    else:
        lines.append("_Documento non disponibile — riprova._")

    if invoice:
        lines.append("")
        lines.append(
            f"💶 **Preventivo:** €{invoice.get('onorario_base_eur', 0):.2f} + IVA "
            f"= **€{invoice.get('totale_eur', 0):.2f}** "
            f"({invoice.get('ore_stimate', '?')}h × €{invoice.get('tariffa_oraria_eur', '?')}/h)"
        )

    response = "\n".join(lines)
    if len(response) > MAX_DISCORD_CHARS:
        response = response[:MAX_DISCORD_CHARS - 100] + "\n\n_[troncato — richiedi il documento completo]_"

    return response, final_state


# ── Discord bot ───────────────────────────────────────────────────────────────

def build_bot() -> "commands.Bot":
    intents           = discord.Intents.default()
    intents.message_content = True
    intents.dm_messages     = True

    bot = commands.Bot(command_prefix="!", intents=intents)
    xbox = XboxPresence(access_token=os.environ.get("XBOX_LIVE_TOKEN"))

    @bot.event
    async def on_ready():
        log.info(f"Avvocato AI online as {bot.user} ({bot.user.id})")
        await bot.change_presence(
            activity=discord.Activity(
                type=discord.ActivityType.listening,
                name="le tue richieste legali ⚖️",
            )
        )

    @bot.event
    async def on_message(message: discord.Message):
        if message.author.bot:
            return

        is_dm      = isinstance(message.channel, discord.DMChannel)
        in_channel = (
            not is_dm
            and CHANNEL_TRIGGER in message.channel.name.lower()
        )

        # Respond only in DMs or in #avvocato channels
        if not (is_dm or in_channel):
            await bot.process_commands(message)
            return

        content = message.content.strip()
        if not content or content.startswith("!"):
            await bot.process_commands(message)
            return

        # Greet on short messages
        if len(content) < 20:
            await message.channel.send(WELCOME_MESSAGE)
            return

        client_name = message.author.display_name

        # Optional: check Xbox presence and add a note
        xbox_note = ""
        xbox_gamertag = getattr(message.author, "_xbox_gamertag", None)
        if xbox_gamertag:
            gaming, title = await xbox.is_gaming(xbox_gamertag)
            if gaming and title:
                xbox_note = f"\n\n🎮 _Ti rispondo mentre sei su Xbox ({title})_"

        async with message.channel.typing():
            try:
                response, _ = await ask_avvocato(content, client_name, "discord")
                response += xbox_note
            except Exception as exc:
                log.exception("Pipeline error")
                response = f"⚠️ Errore nell'elaborare la tua richiesta: {exc}"

        await message.channel.send(response)
        await bot.process_commands(message)

    # ── Slash commands ─────────────────────────────────────────────────────

    @bot.command(name="avvocato", help="Chiedi un parere legale")
    async def cmd_avvocato(ctx: commands.Context, *, domanda: str):
        await ctx.typing()
        try:
            response, _ = await ask_avvocato(domanda, ctx.author.display_name, "discord")
        except Exception as exc:
            response = f"⚠️ Errore: {exc}"
        await ctx.send(response)

    @bot.command(name="materie", help="Elenca le materie legali supportate")
    async def cmd_materie(ctx: commands.Context):
        lines = ["**Materie legali supportate:**"]
        for k, v in MATTER_TYPES.items():
            if k != "unknown":
                rate = BILLING_RATES_IMPORT.get(k, {}).get("hourly", "—")
                lines.append(f"• {v} — €{rate}/h")
        await ctx.send("\n".join(lines))

    @bot.command(name="aiuto", help="Come funziona il bot")
    async def cmd_aiuto(ctx: commands.Context):
        await ctx.send(WELCOME_MESSAGE)

    return bot


# ── Billing rates import (for !materie command) ───────────────────────────────
from state import BILLING_RATES as BILLING_RATES_IMPORT


# ── Entry point ───────────────────────────────────────────────────────────────

def main():
    if not DISCORD_AVAILABLE:
        print("ERROR: discord.py not installed. Run: pip install discord.py")
        sys.exit(1)

    token = os.environ.get("DISCORD_BOT_TOKEN")
    if not token:
        print("ERROR: DISCORD_BOT_TOKEN not set.")
        print("  Get it from: https://discord.com/developers/applications")
        sys.exit(1)

    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        print("ERROR: ANTHROPIC_API_KEY not set.")
        sys.exit(1)

    bot = build_bot()
    log.info("Starting Avvocato AI Discord bot…")
    bot.run(token)


if __name__ == "__main__":
    main()
