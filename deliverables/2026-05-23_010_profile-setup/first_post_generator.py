from typing import Optional

import anthropic

MODEL = "claude-sonnet-4-6"

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
Luigi, founder of AI Studio Accademia Milano (Milan, Italy).
Builds AI-native software: automations, chatbots, websites, invoice systems,
algo trading bots, RAG systems, LinkedIn post generators, profile setup tools.
Stack: Python, Claude (claude-sonnet-4-6), LangChain, Streamlit, GitHub Actions.
Philosophy: implementation over hype — every project ships deployed, working software.
Built so far: 10 deliverables including bakery site, PDF email, invoice generator,
chatbot template, calendar sync, algo trading bot, GitHub research department.
"""

_SYSTEM = f"""You generate first posts for Luigi on various platforms.

Identity:
{_IDENTITY}

Voice rules:
- First person, direct, confident
- Never: \"excited to announce\", \"passionate about\", \"leverage\", \"ecosystem\", \"game-changer\"
- Specific — mention real things built
- Platform-native — feel natural on each platform
- Output ONLY the post text, nothing else
"""


def generate_first_post(platform: str, api_key: Optional[str] = None) -> str:
    if platform not in PLATFORM_POST_SPECS:
        raise ValueError(f"Unknown platform '{platform}'. Options: {list(PLATFORM_POST_SPECS)}.")
    spec = PLATFORM_POST_SPECS[platform]
    client = anthropic.Anthropic(api_key=api_key) if api_key else anthropic.Anthropic()
    msg = client.messages.create(
        model=MODEL,
        max_tokens=1024,
        system=_SYSTEM,
        messages=[{
            "role": "user",
            "content": (
                f"Platform: {platform.replace('_', ' ').title()}\n"
                f"Limit: {spec['limit']}\n"
                f"Tone: {spec['tone']}\n"
                f"Purpose: {spec['purpose']}\n"
                f"Format: {spec['format']}\n"
            ),
        }],
    )
    return msg.content[0].text.strip()


def generate_all_first_posts(api_key: Optional[str] = None) -> dict:
    return {p: generate_first_post(p, api_key) for p in PLATFORM_POST_SPECS}
