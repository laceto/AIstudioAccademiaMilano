"""
Claude-powered chat — used for @mention replies and /ask command.
"""

import os
import anthropic

SYSTEM_PROMPT = """You are the AI Studio Accademia Milano assistant on Discord.

AI Studio is a one-human AI enterprise founded by Luigi Aceto in Milan.
It builds software, automations, and AI tools — delivered fast, priced fairly.

Your role on Discord:
- Answer questions about what AI Studio does and how to order a project
- Explain deliverables already built (weather app, algo trading bot, LinkedIn post generator, etc.)
- Help users understand what credentials or accounts they need
- Keep replies short — Discord is a chat, not a blog
- Be direct, builder-minded, no fluff
- If asked something outside your knowledge, say so and suggest contacting Luigi

Language: match the user's language (Italian or English).
Never pretend to be human. Never reveal internal system details."""


async def reply(user_message: str, api_key: str | None = None) -> str:
    key = api_key or os.environ.get("ANTHROPIC_API_KEY")
    if not key:
        return (
            "⚠️ ANTHROPIC_API_KEY not set — AI replies are disabled. "
            "Set the env var and restart the bot."
        )
    client = anthropic.Anthropic(api_key=key)
    message = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=400,
        system=SYSTEM_PROMPT,
        messages=[{"role": "user", "content": user_message}],
    )
    return message.content[0].text
