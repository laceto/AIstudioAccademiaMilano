from typing import Optional

from openai import OpenAI

MODEL = "gpt-4o"

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
Studio: AI Studio Accademia Milano (Milan, Italy)
What we sell: AI implementation. You bring the idea. We build it and deliver it working.
Two entry points:
  - Physical: anyone with an idea — no technical background required, walk in and leave with a deployed AI product.
  - Digital: businesses and professionals who need AI implemented, not explained or consulted on.
Product model: a fixed catalogue of AI assets at fixed prices. No hourly billing. No proposals. No scope creep.
Asset types: AI chatbots, RAG knowledge bases, automation pipelines, data dashboards,
  agent systems, document generators, API integrations, research tools.
Implementation: no stack limitations — we use AI to build whatever the project requires.
Positioning: we are the first studio in this space. We were shipping working AI products before the market knew it needed them.
Philosophy: implementation over hype. Every engagement ends with deployed, working software.
"""

_SYSTEM = f"""You write platform bios for AI Studio Accademia Milano.

Studio positioning:
{_IDENTITY}

Rules:
- Stay under the character limit (count carefully)
- No: \"passionate about\", \"leveraging\", \"ecosystem\", \"game-changer\", \"excited\", \"solutions\"
- Lead with the product: you bring the idea, we implement it
- Convey the dual channel (physical walk-in + digital) where relevant
- First mover confidence — not arrogant, just matter-of-fact
- Output ONLY the bio text, nothing else
"""


def generate_bio(platform: str, api_key: Optional[str] = None) -> str:
    if platform not in PLATFORM_SPECS:
        raise ValueError(f"Unknown platform '{platform}'. Options: {list(PLATFORM_SPECS)}.")
    spec = PLATFORM_SPECS[platform]
    client = OpenAI(api_key=api_key) if api_key else OpenAI()
    resp = client.chat.completions.create(
        model=MODEL,
        max_tokens=600,
        messages=[
            {"role": "system", "content": _SYSTEM},
            {
                "role": "user",
                "content": (
                    f"Platform: {platform.replace('_', ' ').title()}\n"
                    f"Max characters: {spec['max_chars']}\n"
                    f"Tone: {spec['tone']}\n"
                    f"Format: {spec['format']}\n"
                ),
            },
        ],
    )
    return resp.choices[0].message.content.strip()


def generate_all_bios(api_key: Optional[str] = None) -> dict:
    return {p: generate_bio(p, api_key) for p in PLATFORM_SPECS}
