import argparse
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from search_repos import search_all_topics, AI_TOPICS
from evaluate_repo import rank_repos
from report import deduplicate, generate_report
from search_users import search_contributors, DEFAULT_QUERY
from score_user import rank_users
from report_users import generate_contributor_report


def run_repos(args, token):
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
    print("\nTop 5 repos:")
    for rs in top5:
        print(f"  [{rs.tier}] {rs.repo.full_name}  {rs.repo.stars:,} stars  {rs.score}/100")


def run_contributors(args, token):
    query = getattr(args, "query", DEFAULT_QUERY)
    scan_readmes = getattr(args, "scan_readmes", False)
    max_results = getattr(args, "max_results", 30)

    print(f"[ContributorScout] Searching users (max {max_results})...")
    profiles = search_contributors(
        query=query,
        token=token,
        max_results=max_results,
        scan_readmes=scan_readmes,
    )
    print(f"  -> {len(profiles)} profiles enriched")

    print("[ContributorScout] Scoring users...")
    scored = rank_users(profiles)

    contributor_output = args.output.parent / "contributor_report.md"
    print("[ContributorScout] Generating report...")
    generate_contributor_report(scored, output_path=contributor_output)

    top5 = scored[:5]
    print("\nTop 5 potential clients:")
    for us in top5:
        needs = ", ".join(us.needs_inferred[:2]) or "unknown"
        print(f"  [{us.tier}] {us.profile.login}  score={us.score}  needs={needs}")


def main():
    parser = argparse.ArgumentParser(description="GitHub AI Research Team CLI")
    parser.add_argument("--mode", choices=["repos", "contributors", "both"], default="repos",
                        help="repos: repo research only | contributors: client prospecting | both: run both")
    parser.add_argument("--topics", nargs="+", default=AI_TOPICS[:6])
    parser.add_argument("--min-stars", type=int, default=100)
    parser.add_argument("--max-per-topic", type=int, default=10)
    parser.add_argument("--output", type=Path, default=Path("research_report.md"))
    # Contributor-specific flags
    parser.add_argument("--query", default=DEFAULT_QUERY, help="GitHub user search query")
    parser.add_argument("--max-results", type=int, default=30, help="Max users to enrich")
    parser.add_argument("--scan-readmes", action="store_true",
                        help="Scan repo READMEs for AI keywords (slower, needs token)")
    args = parser.parse_args()

    token = os.environ.get("RESEARCH_GITHUB_TOKEN") or os.environ.get("GITHUB_TOKEN")
    if not token:
        print("[Research] No token set — unauthenticated (60 req/h). Results will be limited.")

    if args.mode in ("repos", "both"):
        run_repos(args, token)

    if args.mode in ("contributors", "both"):
        run_contributors(args, token)


if __name__ == "__main__":
    main()
