from typing import Optional

import anthropic

MODEL = "claude-sonnet-4-6"

PLATFORM_SPECS = {
    "linkedin_headline": {
        "max_chars": 220,
        "tone": "professional, founder-level, specific",
        "format": "Role | What you build | Unique angle",
    },
    "linkedin_about": {
        "max_chars": 2600,
        "tone": "professional but direct, first person, builder's voice",
        "format": "3-4 short paragraphs: what you do, how you do it, what you've shipped, call to connect",
    },
    "twitter_x": {
        "max_chars": 160,
        "tone": "punchy, no fluff, builder identity",
        "format": "What you build + where. No hashtags in bio.",
    },
    "github": {
        "max_chars": 255,
        "tone": "technical, direct, open-source friendly",
        "format": "Who you are + what you build + stack or approach",
    },
    "instagram": {
        "max_chars": 150,
        "tone": "visual, atelier identity, creative but grounded",
        "format": "3-4 short lines. Emoji optional. End with ↓ link in bio.",
    },
    "discord_server": {
        "max_chars": 190,
        "tone": "community-friendly, expert, welcoming",
        "format": "What the server is + what members get from joining",
    },
    "reddit": {
        "max_chars": 200,
        "tone": "casual, genuine, zero marketing speak",
        "format": "Who you are + what you're building + why you're on Reddit",
    },
    "product_hunt": {
        "max_chars": 200,
        "tone": "maker community, product-focused, real",
        "format": "What you make + your building approach",
    },
    "telegram": {
        "max_chars": 70,
        "tone": "ultra-concise, identity-first",
        "format": "One-liner. Who you are + what this channel is.",
    },
}

_IDENTITY = """
Name: Luigi
Company: AI Studio Accademia Milano (Milan, Italy)
What: AI-native software production — one human + AI agents building at industrial scale
Stack: Python, Claude, LangChain, Streamlit, FastAPI, GitHub Actions
Built so far: bakery website, PDF email sender, invoice generator, chatbot template,
  calendar sync, algo trading bot (Alpaca paper), GitHub research department,
  LinkedIn post generator, profile setup automation
Philosophy: implementation over hype — every project ships deployed, working software
Mission: raise economic value through AI implementation
Voice: direct, builder, no corporate speak, no buzzwords
"""

_SYSTEM = f"""You write platform bios for Luigi, founder of AI Studio Accademia Milano.

Identity:
{_IDENTITY}

Rules:
- Stay under the character limit (count carefully)
- No: \"passionate about\", \"leveraging\", \"ecosystem\", \"game-changer\", \"excited\"
- Be specific — mention actual things built when relevant
- Feel native to each platform
- Output ONLY the bio text, nothing else
"""


def generate_bio(platform: str, api_key: Optional[str] = None) -> str:
    if platform not in PLATFORM_SPECS:
        raise ValueError(f"Unknown platform '{platform}'. Options: {list(PLATFORM_SPECS)}.")
    spec = PLATFORM_SPECS[platform]
    client = anthropic.Anthropic(api_key=api_key) if api_key else anthropic.Anthropic()
    msg = client.messages.create(
        model=MODEL,
        max_tokens=600,
        system=_SYSTEM,
        messages=[{
            "role": "user",
            "content": (
                f"Platform: {platform.replace('_', ' ').title()}\n"
                f"Max characters: {spec['max_chars']}\n"
                f"Tone: {spec['tone']}\n"
                f"Format: {spec['format']}\n"
            ),
        }],
    )
    return msg.content[0].text.strip()


def generate_all_bios(api_key: Optional[str] = None) -> dict:
    return {p: generate_bio(p, api_key) for p in PLATFORM_SPECS}
