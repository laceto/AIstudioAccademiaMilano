"""
AI Studio Accademia Milano — Digital Presence Pipeline

Bridges D009 (LinkedIn post generator) with D010 (Valentina publisher).
Reads GitHub activity → generates post via Claude → auto-publishes to configured platforms.

Usage:
    python scripts/digital_presence_pipeline.py
    python scripts/digital_presence_pipeline.py --days 14 --platforms telegram,twitter_x
    python scripts/digital_presence_pipeline.py --dry-run
    python scripts/digital_presence_pipeline.py --repo laceto/some-other-repo --platforms discord
"""
import argparse
import datetime
import json
import os
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).parent.parent
D009 = REPO_ROOT / "deliverables" / "2026-05-23_009_linkedin-post-generator"
D010 = REPO_ROOT / "deliverables" / "2026-05-23_010_profile-setup"

sys.path.insert(0, str(REPO_ROOT))
sys.path.insert(0, str(D009))
sys.path.insert(0, str(D010))

from config.brand import b

DEFAULT_REPO = b("github.full_repo")
OUTPUT_DIR = REPO_ROOT / "process" / "digital-presence"
RUN_LOG = OUTPUT_DIR / "run_log.json"


def _ensure_dirs():
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)


def _log_run(entry: dict):
    log = json.loads(RUN_LOG.read_text()) if RUN_LOG.exists() else []
    log.append(entry)
    RUN_LOG.write_text(json.dumps(log, indent=2))


def run(
    repo: str,
    days: int,
    platforms: list[str],
    dry_run: bool,
    output_file: Path,
):
    from github_reader import build_activity_summary
    from post_generator import generate_linkedin_post
    from publisher import PUBLISHER_MAP, MANUAL_PLATFORMS

    ts = datetime.datetime.utcnow().isoformat()
    print(f"\n[{ts}] Digital Presence Pipeline")
    print(f"  Repo   : {repo}  (last {days} days)")
    print(f"  Targets: {', '.join(platforms) if platforms else 'generate only'}")
    print(f"  Mode   : {'DRY RUN' if dry_run else 'LIVE'}\n")

    # ── Step 1: fetch GitHub activity ──────────────────────────────────────────
    print("1/3  Fetching GitHub activity...")
    try:
        summary = build_activity_summary(
            *repo.split("/"),
            token=os.environ.get("GITHUB_TOKEN"),
            since_days=days,
        )
    except Exception as exc:
        print(f"     ERROR: {exc}")
        sys.exit(1)

    n_commits = len(summary["commits"])
    n_releases = len(summary["releases"])
    print(f"     {n_commits} commit(s)  {n_releases} release(s)")

    if n_commits == 0 and n_releases == 0:
        print(f"     No activity in the last {days} days — try --days 30")
        sys.exit(0)

    # ── Step 2: generate post ──────────────────────────────────────────────────
    print("2/3  Generating post with Claude...")
    try:
        post = generate_linkedin_post(summary)
    except Exception as exc:
        print(f"     ERROR: {exc}")
        sys.exit(1)

    _ensure_dirs()
    output_file.write_text(post, encoding="utf-8")
    print(f"     Saved → {output_file.relative_to(REPO_ROOT)}")

    print()
    print("─" * 60)
    print(post)
    print("─" * 60)

    # ── Step 3: publish ────────────────────────────────────────────────────────
    results = {}

    auto_platforms = [p for p in platforms if p in PUBLISHER_MAP]
    manual_platforms = [p for p in platforms if p in MANUAL_PLATFORMS]
    unknown_platforms = [p for p in platforms if p not in PUBLISHER_MAP and p not in MANUAL_PLATFORMS]

    if unknown_platforms:
        print(f"\nWARN: unknown platforms skipped: {', '.join(unknown_platforms)}")

    print(f"\n3/3  Publishing to {len(auto_platforms)} auto + {len(manual_platforms)} manual platform(s)...")

    for p in auto_platforms:
        if dry_run:
            print(f"     [DRY RUN] {p} — skipped")
            results[p] = "dry_run"
            continue
        try:
            result = PUBLISHER_MAP[p](post)
            print(f"     {p} ✓  {result}")
            results[p] = result
        except Exception as exc:
            print(f"     {p} ✗  {exc}")
            results[p] = f"error: {exc}"

    for p in manual_platforms:
        print(f"\n  {p.upper()} — manual posting required")
        print(f"  {MANUAL_PLATFORMS[p]}")
        print(f"  Post text saved to: {output_file}")
        results[p] = "manual"

    # LinkedIn is always shown if not in platforms list
    if "linkedin" not in platforms:
        print(f"\n  LINKEDIN — paste manually at linkedin.com/feed/")
        print(f"  Post text: {output_file}")

    # ── Log run ────────────────────────────────────────────────────────────────
    _log_run({
        "ts": ts,
        "repo": repo,
        "days": days,
        "commits": n_commits,
        "releases": n_releases,
        "dry_run": dry_run,
        "platforms": results,
        "output": str(output_file),
    })

    print(f"\nDone. Run logged to {RUN_LOG.relative_to(REPO_ROOT)}")


def main():
    parser = argparse.ArgumentParser(description="Digital Presence Pipeline")
    parser.add_argument("--repo", default=DEFAULT_REPO, help="GitHub repo (owner/name)")
    parser.add_argument("--days", type=int, default=7, help="Activity look-back window (default: 7)")
    parser.add_argument(
        "--platforms",
        default="",
        help="Comma-separated publish targets: telegram,twitter_x,discord,reddit,linkedin",
    )
    parser.add_argument("--dry-run", action="store_true", help="Generate post but skip publishing")
    parser.add_argument("--output", default=None, help="Output file for LinkedIn post text")
    args = parser.parse_args()

    platforms = [p.strip() for p in args.platforms.split(",") if p.strip()]
    date_str = datetime.date.today().isoformat()
    output_file = (
        Path(args.output)
        if args.output
        else OUTPUT_DIR / f"{date_str}_linkedin_post.txt"
    )

    run(
        repo=args.repo,
        days=args.days,
        platforms=platforms,
        dry_run=args.dry_run,
        output_file=output_file,
    )


if __name__ == "__main__":
    main()
