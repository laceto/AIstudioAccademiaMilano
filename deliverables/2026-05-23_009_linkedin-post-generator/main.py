"""
AI Studio Accademia Milano — LinkedIn Post Generator

Reads recent commits and releases from a GitHub repo and generates
a ready-to-publish LinkedIn post in Luigi's voice using Claude.

Usage:
    python main.py --repo laceto/hello-world
    python main.py --repo laceto/hello-world --days 60 --copy
    python main.py --repo laceto/aistudioaccademiamilano --output post.txt
"""
import argparse
import os
import sys

from github_reader import build_activity_summary
from post_generator import generate_linkedin_post


def main():
    parser = argparse.ArgumentParser(
        description="Generate a LinkedIn post from recent GitHub activity"
    )
    parser.add_argument(
        "--repo", required=True,
        help="GitHub repo in owner/name format (e.g. laceto/hello-world)"
    )
    parser.add_argument(
        "--days", type=int, default=30,
        help="Look back N days for commits (default: 30)"
    )
    parser.add_argument(
        "--token", default=None,
        help="GitHub token (or set GITHUB_TOKEN env var). Raises rate limit from 60 to 5000 req/h."
    )
    parser.add_argument(
        "--api-key", default=None,
        help="Anthropic API key (or set ANTHROPIC_API_KEY env var)"
    )
    parser.add_argument(
        "--output", default="linkedin_post.txt",
        help="Output file path (default: linkedin_post.txt)"
    )
    parser.add_argument(
        "--copy", action="store_true",
        help="Copy the generated post to clipboard"
    )
    args = parser.parse_args()

    parts = args.repo.strip().split("/")
    if len(parts) != 2 or not all(parts):
        print("Error: --repo must be owner/name, e.g. laceto/hello-world")
        sys.exit(1)
    owner, repo = parts

    # Fetch GitHub activity
    print(f"\nFetching activity from {args.repo} (last {args.days} days)...")
    try:
        summary = build_activity_summary(owner, repo, token=args.token, since_days=args.days)
    except Exception as e:
        print(f"Error fetching GitHub data: {e}")
        sys.exit(1)

    n_commits = len(summary["commits"])
    n_releases = len(summary["releases"])
    repo_info = summary["repo"]
    print(f"  {repo_info['full_name']} — {repo_info['description'] or 'no description'}")
    print(f"  {n_commits} commit(s) | {n_releases} release(s) | language: {repo_info['language']}")

    if n_commits == 0 and n_releases == 0:
        print(f"\nNo activity found in the last {args.days} days.")
        print("Try a longer window with --days 90")
        sys.exit(0)

    # Generate post
    print("\nGenerating LinkedIn post with Claude...")
    try:
        post = generate_linkedin_post(summary, api_key=args.api_key)
    except Exception as e:
        print(f"Error generating post: {e}")
        sys.exit(1)

    # Save to file
    with open(args.output, "w", encoding="utf-8") as f:
        f.write(post)
    print(f"Post saved to: {args.output}")

    # Print
    print()
    print("─" * 60)
    print(post)
    print("─" * 60)

    # Clipboard
    if args.copy:
        try:
            import pyperclip
            pyperclip.copy(post)
            print("\n✓ Copied to clipboard.")
        except ImportError:
            print("\nInstall pyperclip to use --copy: pip install pyperclip")
        except Exception as e:
            print(f"\nCould not copy to clipboard: {e}")


if __name__ == "__main__":
    main()
