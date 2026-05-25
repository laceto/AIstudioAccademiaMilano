"""
github_delta/collect.py — Daily GitHub activity delta collector

Polls the GitHub Events API for this repo, categorises each event, writes a
daily snapshot to process/github_delta/YYYY-MM-DD.json, and computes the
day-over-day delta. Updates global_settings.json["github_activity_counters"].

Categories tracked:
  commit        PushEvent (one entry per distinct commit sha)
  pr_open       PullRequestEvent action=opened
  pr_close      PullRequestEvent action=closed (not merged)
  pr_merge      PullRequestEvent action=closed + merged=true
  issue_open    IssuesEvent action=opened
  issue_close   IssuesEvent action=closed
  issue_comment IssueCommentEvent
  review        PullRequestReviewEvent
  branch_create CreateEvent ref_type=branch
  branch_delete DeleteEvent ref_type=branch
  release       ReleaseEvent
  deploy        DeploymentEvent / DeploymentStatusEvent

Usage:
    python -m scripts.github_delta.collect              # collect today + update settings
    python -m scripts.github_delta.collect --report     # print delta report to stdout
    python -m scripts.github_delta.collect --date 2026-05-24  # backfill a specific date
"""

import argparse
import json
import os
import sys
from datetime import date, timedelta
from pathlib import Path
from typing import Optional

import requests

ROOT = Path(__file__).parent.parent.parent
DELTA_DIR = ROOT / "process" / "github_delta"
SETTINGS_PATH = ROOT / "config" / "global_settings.json"

GITHUB_API = "https://api.github.com"
REPO = "laceto/AIstudioAccademiaMilano"

CATEGORIES = [
    "commit", "pr_open", "pr_close", "pr_merge",
    "issue_open", "issue_close", "issue_comment",
    "review", "branch_create", "branch_delete",
    "release", "deploy",
]

EVENT_MAP = {
    "PushEvent":                  None,   # handled specially (per-commit)
    "PullRequestEvent":           None,   # handled specially (open/close/merge)
    "IssuesEvent":                None,   # handled specially (open/close)
    "IssueCommentEvent":          "issue_comment",
    "PullRequestReviewEvent":     "review",
    "CreateEvent":                None,   # handled specially (branch vs tag)
    "DeleteEvent":                None,   # handled specially (branch vs tag)
    "ReleaseEvent":               "release",
    "DeploymentEvent":            "deploy",
    "DeploymentStatusEvent":      "deploy",
}


def _headers() -> dict:
    token = os.environ.get("GITHUB_TOKEN", "")
    h = {
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
    }
    if token:
        h["Authorization"] = f"Bearer {token}"
    return h


def _empty_counts() -> dict:
    return {cat: 0 for cat in CATEGORIES}


def _fetch_events(target_date: date) -> list[dict]:
    """Fetch all events for the repo on target_date (UTC). Paginates up to 10 pages."""
    events = []
    target_str = target_date.isoformat()
    next_str = (target_date + timedelta(days=1)).isoformat()

    for page in range(1, 11):
        url = f"{GITHUB_API}/repos/{REPO}/events"
        resp = requests.get(url, headers=_headers(),
                            params={"per_page": 100, "page": page}, timeout=15)
        if resp.status_code == 422:
            break  # beyond available history
        resp.raise_for_status()
        page_events = resp.json()
        if not page_events:
            break

        for ev in page_events:
            created = ev.get("created_at", "")[:10]
            if created < target_str:
                # Events are newest-first; once we're past target date, stop
                return events
            if created == target_str:
                events.append(ev)
        # If last event on page is still >= target, continue paginating
        if page_events and page_events[-1].get("created_at", "")[:10] >= target_str:
            continue
        break

    return events


def _categorise(events: list[dict]) -> dict:
    counts = _empty_counts()
    seen_commits: set = set()
    actors: dict = {}

    for ev in events:
        etype = ev.get("type", "")
        actor = ev.get("actor", {}).get("login", "unknown")
        payload = ev.get("payload", {})

        if etype == "PushEvent":
            for commit in payload.get("commits", []):
                sha = commit.get("sha", "")
                if sha and sha not in seen_commits:
                    seen_commits.add(sha)
                    counts["commit"] += 1
                    actors.setdefault("commit", [])
                    if actor not in actors["commit"]:
                        actors["commit"].append(actor)

        elif etype == "PullRequestEvent":
            action = payload.get("action", "")
            pr = payload.get("pull_request", {})
            if action == "opened":
                counts["pr_open"] += 1
            elif action == "closed":
                if pr.get("merged"):
                    counts["pr_merge"] += 1
                else:
                    counts["pr_close"] += 1

        elif etype == "IssuesEvent":
            action = payload.get("action", "")
            if action == "opened":
                counts["issue_open"] += 1
            elif action == "closed":
                counts["issue_close"] += 1

        elif etype == "CreateEvent":
            if payload.get("ref_type") == "branch":
                counts["branch_create"] += 1

        elif etype == "DeleteEvent":
            if payload.get("ref_type") == "branch":
                counts["branch_delete"] += 1

        elif etype in EVENT_MAP and EVENT_MAP[etype]:
            cat = EVENT_MAP[etype]
            counts[cat] += 1

    return {"counts": counts, "actors": actors}


def _load_snapshot(target_date: date) -> Optional[dict]:
    path = DELTA_DIR / f"{target_date.isoformat()}.json"
    if path.exists():
        return json.loads(path.read_text(encoding="utf-8"))
    return None


def _save_snapshot(target_date: date, data: dict) -> None:
    DELTA_DIR.mkdir(parents=True, exist_ok=True)
    path = DELTA_DIR / f"{target_date.isoformat()}.json"
    path.write_text(json.dumps(data, indent=2), encoding="utf-8")


def _compute_delta(today: dict, yesterday: Optional[dict]) -> dict:
    if yesterday is None:
        return {cat: today["counts"].get(cat, 0) for cat in CATEGORIES}
    return {
        cat: today["counts"].get(cat, 0) - yesterday["counts"].get(cat, 0)
        for cat in CATEGORIES
    }


def _update_settings(snapshot: dict) -> None:
    """Merge today's counts into global_settings.json github_activity_counters."""
    try:
        text = SETTINGS_PATH.read_text(encoding="utf-8")
        settings = json.loads(text)
    except Exception:
        return

    counters = settings.setdefault("github_activity_counters", {cat: 0 for cat in CATEGORIES})
    for cat, n in snapshot["counts"].items():
        counters[cat] = counters.get(cat, 0) + n

    SETTINGS_PATH.write_text(json.dumps(settings, indent=2, ensure_ascii=False), encoding="utf-8")


def _print_report(target_date: date, snapshot: dict, delta: dict) -> None:
    print(f"\n=== GitHub Delta Report: {target_date} ===")
    print(f"{'Category':<18} {'Today':>6}  {'Delta':>7}")
    print("-" * 36)
    for cat in CATEGORIES:
        count = snapshot["counts"].get(cat, 0)
        d = delta.get(cat, 0)
        sign = "+" if d > 0 else ""
        print(f"  {cat:<16} {count:>6}  {sign}{d:>6}")
    total = sum(snapshot["counts"].get(c, 0) for c in CATEGORIES)
    total_delta = sum(delta.values())
    sign = "+" if total_delta > 0 else ""
    print("-" * 36)
    print(f"  {'TOTAL':<16} {total:>6}  {sign}{total_delta:>6}")

    actors = snapshot.get("actors", {})
    if actors:
        print(f"\nActors today: {', '.join(set(a for lst in actors.values() for a in lst))}")
    print()


def collect(target_date: date, report: bool = False) -> dict:
    print(f"[github_delta] Collecting events for {target_date}...")
    events = _fetch_events(target_date)
    print(f"[github_delta] {len(events)} events found")

    data = _categorise(events)
    data["date"] = target_date.isoformat()
    data["event_count_raw"] = len(events)

    yesterday = _load_snapshot(target_date - timedelta(days=1))
    delta = _compute_delta(data, yesterday)
    data["delta"] = delta

    _save_snapshot(target_date, data)
    _update_settings(data)

    if report:
        _print_report(target_date, data, delta)

    print(f"[github_delta] Snapshot saved -> process/github_delta/{target_date}.json")
    return data


def main() -> None:
    parser = argparse.ArgumentParser(description="Collect daily GitHub event delta")
    parser.add_argument("--date", help="Target date YYYY-MM-DD (default: today)")
    parser.add_argument("--report", action="store_true", help="Print delta report to stdout")
    args = parser.parse_args()

    target = date.fromisoformat(args.date) if args.date else date.today()
    collect(target, report=args.report)


if __name__ == "__main__":
    main()
