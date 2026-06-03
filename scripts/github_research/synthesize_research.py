"""
synthesize_research.py — AI-powered repo insight synthesis via kitai batch.

Runs only on GitHub Actions when OPENAI_API_KEY is set (50% cheaper batch API).
Returns {} silently in all other contexts — no dependency on kitai locally.

Usage (called automatically by main.py when on GA):
    from synthesize_research import synthesize_repo_insights
    insights = synthesize_repo_insights(top_repo_scores)
    # insights = {"owner/repo": "2-3 sentence insight", ...}
"""
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

MODEL = "gpt-4o-mini"

SYSTEM_PROMPT = (
    "You are an AI research analyst for AI Studio Accademia Milano. "
    "Given a GitHub repository's metadata, write exactly 2-3 sentences explaining:\n"
    "1. What specific problem it solves\n"
    "2. Why it matters for AI builders right now\n"
    "3. One concrete use case\n\n"
    "Be technical and direct. No hype. Under 100 words. No bullet points."
)


def _is_ga_batch() -> bool:
    return (
        os.environ.get("GITHUB_ACTIONS") == "true"
        and bool(os.environ.get("OPENAI_API_KEY"))
    )


def synthesize_repo_insights(repo_scores: list, max_repos: int = 20) -> dict[str, str]:
    """Return {full_name: insight_text} for up to max_repos top-scored repos.

    Only runs on GitHub Actions with OPENAI_API_KEY set. Returns {} otherwise.
    """
    if not _is_ga_batch():
        return {}

    from scripts.batch_utils import submit_and_wait

    top = sorted(repo_scores, key=lambda x: x.score, reverse=True)[:max_repos]
    if not top:
        return {}

    tasks = []
    for rs in top:
        repo = rs.repo
        user_msg = (
            f"Name: {repo.full_name}\n"
            f"Description: {repo.description or 'none'}\n"
            f"Stars: {repo.stars:,} | Forks: {repo.forks} | Language: {repo.language}\n"
            f"Topics: {', '.join(repo.topics[:8]) or 'none'}\n"
            f"Score: {rs.score}/100 (tier {rs.tier})\n\n"
            "Write the 2-3 sentence insight."
        )
        tasks.append({
            "custom_id": repo.full_name.replace("/", "__"),
            "method": "POST",
            "url": "/v1/chat/completions",
            "body": {
                "model": MODEL,
                "temperature": 0,
                "max_tokens": 150,
                "messages": [
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user",   "content": user_msg},
                ],
            },
        })

    print(f"[Synthesizer] Submitting {len(tasks)} repo insights to kitai batch...")
    try:
        results = submit_and_wait(tasks, poll_interval=30.0)
    except Exception as exc:
        print(f"[Synthesizer] Batch failed — skipping AI summaries: {exc}")
        return {}

    insights: dict[str, str] = {}
    for item in results:
        cid = item.get("custom_id", "")
        full_name = cid.replace("__", "/")
        try:
            content = item["response"]["body"]["choices"][0]["message"]["content"]
            insights[full_name] = content.strip()
        except Exception:
            pass

    print(f"[Synthesizer] {len(insights)}/{len(tasks)} insights generated.")
    return insights
