from typing import Optional

from openai import OpenAI

MODEL = "gpt-4o"

PLATFORM_POST_SPECS = {
    "linkedin": {
        "limit": "250 words max",
        "tone": "professional, builder, first-person",
        "purpose": "Announce AI Studio is active on LinkedIn. Introduce Luigi, what the studio does, what followers will get.",
        "format": "Hook + what you do + what you'll share + call to follow. End with 3-5 hashtags.",
    },
    "twitter_x": {
        "limit": "280 characters",
        "tone": "punchy, direct, zero fluff",
        "purpose": "First tweet. Make it worth following.",
        "format": "1-2 sentences. What this account is. Optional: what to expect.",
    },
    "twitter_x_intro_thread": {
        "limit": "280 chars per tweet, 5 tweets",
        "tone": "technical storytelling, thread format",
        "purpose": "Intro thread. Tell the AI Studio story: what it is, how it works, what's built, what's coming.",
        "format": "5 tweets numbered 1/ through 5/. Each self-contained but builds. End with follow CTA.",
    },
    "github_profile_readme": {
        "limit": "400 words max",
        "tone": "technical, clear, open-source community",
        "purpose": "GitHub profile README.md. Introduces Luigi, links to key projects.",
        "format": "Valid Markdown. Brief intro, what you build, list of key deliverables with one-line descriptions, contact. No more than 3 H2 headers.",
    },
    "discord_welcome": {
        "limit": "150 words max",
        "tone": "welcoming, community-focused, expert",
        "purpose": "Pinned welcome message in #welcome channel.",
        "format": "Welcome + what the server is about + channel guide (3-4 channels) + how to get started.",
    },
    "reddit_intro": {
        "limit": "250 words max",
        "tone": "genuine, no marketing, community-first",
        "purpose": "First post introducing AI Studio. Suitable for r/MachineLearning, r/artificial, or r/startups.",
        "format": "Conversational. What you're building, why, honest observations. Invite discussion.",
    },
    "instagram_first": {
        "limit": "2200 chars, caption + hashtags",
        "tone": "visual-first, atelier identity, creative but real",
        "purpose": "First Instagram post. Accompanies a workspace or build-in-progress photo.",
        "format": "3-4 lines caption + blank line + 20-25 hashtags.",
    },
    "telegram_pinned": {
        "limit": "120 words max",
        "tone": "direct, subscriber-focused, informative",
        "purpose": "Pinned welcome message for AI Studio Telegram channel.",
        "format": "What this channel is + what subscribers get + how often updates land.",
    },
    "product_hunt_maker": {
        "limit": "150 words max",
        "tone": "maker community, launch-focused, genuine",
        "purpose": "Maker intro shown on Product Hunt launches.",
        "format": "Who you are + what you've built + why Product Hunt.",
    },
}

_IDENTITY = """
AI Studio Accademia Milano (Milan, Italy).
What we sell: AI implementation. You bring the idea. We build it and deliver it working.
Two entry points:
  - Physical: anyone with an idea — no technical knowledge needed. Walk in, leave with a deployed AI product.
  - Digital: businesses and professionals who need AI built, not explained.
Product model: fixed catalogue of AI assets, fixed prices, fast delivery. No proposals, no hourly billing.
Asset types: AI chatbots, RAG knowledge bases, automation pipelines, data dashboards,
  agent systems, document generators, API integrations, research tools.
Implementation: no stack limitations — we use AI to build whatever the project requires.
Positioning: first mover. We were shipping working AI products before the market had a name for it.
"""

_SYSTEM = f"""You generate first posts for AI Studio Accademia Milano on various platforms.

Studio positioning:
{_IDENTITY}

Voice rules:
- Short sentences. Direct. No filler words.
- Do NOT introduce any person by name. No \"I'm Luigi\", no \"meet [name]\".
- Do NOT say \"our team\" — one founder, AI agents. No team.
- Do NOT say: \"excited\", \"thrilled\", \"passionate\", \"leverage\", \"ecosystem\", \"game-changer\",
  \"solutions\", \"cutting-edge\", \"transforming\", \"turn your ideas into reality\",
  \"bringing ideas to life\", \"sneak peek\", \"stay ahead\", \"insights\", \"journey\",
  \"empower\", \"unlock\", \"seamless\", \"innovative\", \"from day one\", \"where ideas meet\"
- Use only straight apostrophes ('). No curly quotes. No special characters.
- Output ONLY the post text. Nothing else.

Tone example (use this as a model, do not copy it):
\"We have been building AI products for months. No announcements, no decks. Just shipping.
RAG systems, chatbots, automation pipelines, agent teams. Fixed price. Working on delivery.
We are on LinkedIn now. If you have an idea that needs AI to work, this is the place.
#AIImplementation #Milan #BuildDontTalk\"

The example above shows: matter-of-fact, short, specific about what we build, no personal introductions, no marketing language.
"""


def generate_first_post(platform: str, api_key: Optional[str] = None) -> str:
    if platform not in PLATFORM_POST_SPECS:
        raise ValueError(f"Unknown platform '{platform}'. Options: {list(PLATFORM_POST_SPECS)}.")
    spec = PLATFORM_POST_SPECS[platform]
    client = OpenAI(api_key=api_key) if api_key else OpenAI()
    resp = client.chat.completions.create(
        model=MODEL,
        max_tokens=1024,
        messages=[
            {"role": "system", "content": _SYSTEM},
            {
                "role": "user",
                "content": (
                    f"Platform: {platform.replace('_', ' ').title()}\n"
                    f"Limit: {spec['limit']}\n"
                    f"Tone: {spec['tone']}\n"
                    f"Purpose: {spec['purpose']}\n"
                    f"Format: {spec['format']}\n"
                ),
            },
        ],
    )
    return resp.choices[0].message.content.strip()


def generate_all_first_posts(api_key: Optional[str] = None) -> dict:
    return {p: generate_first_post(p, api_key) for p in PLATFORM_POST_SPECS}
