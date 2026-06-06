import os
from typing import Optional

ANTHROPIC_MODEL = "claude-sonnet-4-6"
OPENAI_MODEL = "gpt-4o"

SYSTEM_PROMPT = """You are Luigi, founder of AI Studio Accademia Milano.

Your voice on LinkedIn:
- First person, direct, confident
- Builder's perspective: you ship things, you don't just talk about them
- Technical enough to be credible, accessible enough for any professional
- No corporate speak. No hollow buzzwords. No "excited to announce".
- Short sentences. Punchy. Real.

Post structure:
1. Hook (1-2 sentences): "I just shipped X." or "Just pushed [X] live."
2. What it does: plain English, 2-4 sentences. Focus on what the user actually gets.
3. Why it matters / what you learned: 2-3 sentences. Be honest.
4. One real observation about building with AI (optional but valued)
5. 3-5 relevant hashtags on the last line

Target: 150-250 words.
Never use: "excited", "thrilled", "leverage", "ecosystem", "game-changer", "seamless".
"""


def _format_activity(summary: dict) -> str:
    repo = summary["repo"]
    commits = summary["commits"]
    releases = summary["releases"]

    lines = [
        f"Repository: {repo['full_name']}",
        f"Description: {repo['description'] or 'not provided'}",
        f"Language: {repo['language']} | Stars: {repo['stars']}",
        f"URL: {repo['url']}",
    ]
    if repo["topics"]:
        lines.append(f"Topics: {', '.join(repo['topics'])}")

    if releases:
        lines.append("\nRecent releases:")
        for rel in releases:
            lines.append(f"  [{rel['tag']}] {rel['name']} ({rel['date'][:10]})")
            if rel["body"]:
                lines.append(f"  Notes: {rel['body'][:300]}")

    if commits:
        lines.append(f"\nRecent commits (last {summary['since_days']} days):")
        for c in commits[:12]:
            lines.append(f"  {c['sha']} {c['date'][:10]} — {c['message']}")

    return "\n".join(lines)


def _generate_with_anthropic(activity_text: str, api_key: Optional[str]) -> str:
    import anthropic
    client = anthropic.Anthropic(api_key=api_key) if api_key else anthropic.Anthropic()
    message = client.messages.create(
        model=ANTHROPIC_MODEL,
        max_tokens=1024,
        system=SYSTEM_PROMPT,
        messages=[{"role": "user", "content": (
            f"Here is the recent GitHub activity:\n\n{activity_text}\n\n"
            "Write a LinkedIn post about this in my voice. "
            "Focus on what was actually built and why it matters. "
            "If commits are small or incremental, find the narrative thread across them."
        )}],
    )
    return message.content[0].text


def _generate_with_openai(activity_text: str, api_key: Optional[str]) -> str:
    from openai import OpenAI
    client = OpenAI(api_key=api_key or os.environ.get("OPENAI_API_KEY"))
    response = client.chat.completions.create(
        model=OPENAI_MODEL,
        max_tokens=1024,
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": (
                f"Here is the recent GitHub activity:\n\n{activity_text}\n\n"
                "Write a LinkedIn post about this in my voice. "
                "Focus on what was actually built and why it matters. "
                "If commits are small or incremental, find the narrative thread across them."
            )},
        ],
    )
    return response.choices[0].message.content


def generate_linkedin_post(
    summary: dict, api_key: Optional[str] = None
) -> str:
    activity_text = _format_activity(summary)
    anthropic_key = api_key or os.environ.get("ANTHROPIC_API_KEY")
    if anthropic_key:
        print("     LLM: Claude (Anthropic)")
        return _generate_with_anthropic(activity_text, anthropic_key)
    openai_key = os.environ.get("OPENAI_API_KEY")
    if openai_key:
        print("     LLM: GPT-4o (OpenAI fallback)")
        return _generate_with_openai(activity_text, openai_key)
    raise RuntimeError(
        'Could not resolve authentication method. Expected one of api_key, auth_token, or credentials to be set. '
        'Set ANTHROPIC_API_KEY or OPENAI_API_KEY.'
    )
