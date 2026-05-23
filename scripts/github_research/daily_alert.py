import argparse
import json
import os
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from search_repos import search_all_topics
from evaluate_repo import rank_repos

DAILY_TOPICS = [
    "llm", "generative-ai", "ai-agents",
    "rag", "multimodal", "fine-tuning",
]
CUTOFF_DAYS = 30


def main():
    parser = argparse.ArgumentParser(description="Daily S-tier alert scanner")
    parser.add_argument("--output", type=Path, default=Path("/tmp/alert.json"))
    parser.add_argument("--cutoff-days", type=int, default=CUTOFF_DAYS)
    args = parser.parse_args()

    token = os.environ.get("RESEARCH_GITHUB_TOKEN") or os.environ.get("GITHUB_TOKEN")
    cutoff = datetime.now(timezone.utc) - timedelta(days=args.cutoff_days)

    print(f"[Scout] Scanning {len(DAILY_TOPICS)} topics for S-tier repos created after {cutoff.date()}")
    raw = search_all_topics(
        topics=DAILY_TOPICS,
        min_stars=200,
        max_per_topic=5,
        token=token,
        delay=1.5,
    )

    seen: dict = {}
    for topic, repos in raw.items():
        for rs in rank_repos(repos):
            if rs.tier != "S":
                continue
            try:
                created = datetime.fromisoformat(rs.repo.created_at.replace("Z", "+00:00"))
            except Exception:
                continue
            if created < cutoff:
                continue
            key = rs.repo.full_name
            if key not in seen or rs.score > seen[key]["score"]:
                seen[key] = {
                    "full_name": rs.repo.full_name,
                    "url": rs.repo.url,
                    "stars": rs.repo.stars,
                    "score": rs.score,
                    "language": rs.repo.language,
                    "description": rs.repo.description,
                    "created_at": rs.repo.created_at,
                    "topic": topic,
                }

    alerts = sorted(seen.values(), key=lambda x: x["score"], reverse=True)
    args.output.write_text(json.dumps({"alerts": alerts}, indent=2), encoding="utf-8")
    print(f"[Analyst] {len(alerts)} new S-tier repo(s) found")


if __name__ == "__main__":
    main()
