"""
post_generator.py — LinkedIn post generation.

On GitHub Actions (GITHUB_ACTIONS=true + OPENAI_API_KEY set):
    → kitai.batch via gpt-4o  (async, 50 % cheaper)

Locally / OPENAI_API_KEY absent:
    → anthropic.Anthropic synchronous (claude-sonnet-4-6, streaming)
"""
import os
import sys
from pathlib import Path
from typing import Optional

MODEL_ANTHROPIC = "claude-sonnet-4-6"
MODEL_BATCH = "gpt-4o"

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

_REPO_ROOT = Path(__file__).parent.parent.parent
sys.path.insert(0, str(_REPO_ROOT))


def _is_ga_batch() -> bool:
    return (
        os.environ.get("GITHUB_ACTIONS") == "true"
        and bool(os.environ.get("OPENAI_API_KEY"))
    )


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


def _user_message(activity_text: str) -> str:
    return (
        f"Here is the recent GitHub activity:\n\n{activity_text}\n\n"
        "Write a LinkedIn post about this in my voice. "
        "Focus on what was actually built and why it matters. "
        "If commits are small or incremental, find the narrative thread across them."
    )


def _generate_via_batch(activity_text: str) -> str:
    """kitai.batch path — GA only, 50% cheaper."""
    from scripts.batch_utils import submit_and_wait

    tasks = [{
        "custom_id": "linkedin-post",
        "method": "POST",
        "url": "/v1/chat/completions",
        "body": {
            "model": MODEL_BATCH,
            "temperature": 0.7,
            "max_tokens": 1024,
            "messages": [
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user",   "content": _user_message(activity_text)},
            ],
        },
    }]

    results = submit_and_wait(tasks, poll_interval=20.0)
    return results[0]["response"]["body"]["choices"][0]["message"]["content"]


def _generate_via_anthropic(activity_text: str, api_key: Optional[str] = None) -> str:
    """Direct Anthropic path — local dev / fallback."""
    import anthropic
    client = anthropic.Anthropic(api_key=api_key) if api_key else anthropic.Anthropic()
    message = client.messages.create(
        model=MODEL_ANTHROPIC,
        max_tokens=1024,
        system=SYSTEM_PROMPT,
        messages=[{"role": "user", "content": _user_message(activity_text)}],
    )
    return message.content[0].text


def generate_linkedin_post(summary: dict, api_key: Optional[str] = None) -> str:
    activity_text = _format_activity(summary)
    if _is_ga_batch():
        print("     [kitai.batch] GA detected — using batch API (gpt-4o)")
        return _generate_via_batch(activity_text)
    return _generate_via_anthropic(activity_text, api_key)
