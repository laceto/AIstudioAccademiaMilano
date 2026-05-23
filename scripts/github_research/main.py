import argparse
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from search_repos import search_all_topics, AI_TOPICS
from evaluate_repo import rank_repos
from report import deduplicate, generate_report


def main():
    parser = argparse.ArgumentParser(description="GitHub AI Research Team CLI")
    parser.add_argument("--topics", nargs="+", default=AI_TOPICS[:6])
    parser.add_argument("--min-stars", type=int, default=100)
    parser.add_argument("--max-per-topic", type=int, default=10)
    parser.add_argument("--output", type=Path, default=Path("research_report.md"))
    args = parser.parse_args()

    # Accept token from RESEARCH_GITHUB_TOKEN or GITHUB_TOKEN
    token = os.environ.get("RESEARCH_GITHUB_TOKEN") or os.environ.get("GITHUB_TOKEN")
    if not token:
        print("[Scout] No token set - using unauthenticated (60 req/h, 10 search req/min)")

    print(f"[Scout] Scanning {len(args.topics)} topics (min {args.min_stars} stars)...")
    raw = search_all_topics(
        topics=args.topics,
        min_stars=args.min_stars,
        max_per_topic=args.max_per_topic,
        token=token,
    )
    print(f"  -> {sum(len(v) for v in raw.values())} repos found")

    print("[Analyst] Scoring repos...")
    ranked = {topic: rank_repos(repos) for topic, repos in raw.items()}

    print("[Curator] Deduplicating and categorising...")
    categorised = deduplicate(ranked)
    print(f"  -> {sum(len(v) for v in categorised.values())} unique repos across {len(categorised)} categories")

    print("[Reporter] Generating report...")
    generate_report(categorised, output_path=args.output)
    print(f"  -> Report written to {args.output}")

    all_scored = [rs for v in categorised.values() for rs in v]
    top5 = sorted(all_scored, key=lambda x: x.score, reverse=True)[:5]
    print("\nTop 5:")
    for rs in top5:
        print(f"  [{rs.tier}] {rs.repo.full_name}  {rs.repo.stars:,} stars  {rs.score}/100")


if __name__ == "__main__":
    main()
