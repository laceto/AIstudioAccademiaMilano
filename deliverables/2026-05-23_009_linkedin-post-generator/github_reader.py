import os
from datetime import datetime, timedelta, timezone
from typing import Optional

import requests


def _headers(token: Optional[str] = None) -> dict:
    h = {"Accept": "application/vnd.github+json", "X-GitHub-Api-Version": "2022-11-28"}
    tok = token or os.environ.get("GITHUB_TOKEN") or os.environ.get("RESEARCH_GITHUB_TOKEN")
    if tok:
        h["Authorization"] = f"Bearer {tok}"
    return h


def fetch_repo_info(owner: str, repo: str, token: Optional[str] = None) -> dict:
    url = f"https://api.github.com/repos/{owner}/{repo}"
    r = requests.get(url, headers=_headers(token), timeout=10)
    r.raise_for_status()
    data = r.json()
    return {
        "full_name": data["full_name"],
        "description": data.get("description") or "",
        "language": data.get("language") or "unknown",
        "stars": data.get("stargazers_count", 0),
        "url": data["html_url"],
        "topics": data.get("topics", []),
    }


def fetch_recent_commits(
    owner: str,
    repo: str,
    token: Optional[str] = None,
    since_days: int = 30,
    limit: int = 15,
) -> list:
    since = (datetime.now(timezone.utc) - timedelta(days=since_days)).isoformat()
    url = f"https://api.github.com/repos/{owner}/{repo}/commits"
    r = requests.get(
        url, headers=_headers(token), params={"since": since, "per_page": limit}, timeout=10
    )
    r.raise_for_status()
    commits = []
    for c in r.json():
        commit = c.get("commit", {})
        commits.append({
            "sha": c["sha"][:7],
            "message": commit.get("message", "").split("\n")[0],
            "date": commit.get("author", {}).get("date", ""),
            "author": commit.get("author", {}).get("name", ""),
        })
    return commits


def fetch_recent_releases(
    owner: str, repo: str, token: Optional[str] = None, limit: int = 3
) -> list:
    url = f"https://api.github.com/repos/{owner}/{repo}/releases"
    r = requests.get(
        url, headers=_headers(token), params={"per_page": limit}, timeout=10
    )
    r.raise_for_status()
    releases = []
    for rel in r.json():
        releases.append({
            "tag": rel.get("tag_name", ""),
            "name": rel.get("name", ""),
            "body": (rel.get("body") or "")[:500],
            "date": rel.get("published_at", ""),
            "url": rel.get("html_url", ""),
        })
    return releases


def build_activity_summary(
    owner: str, repo: str, token: Optional[str] = None, since_days: int = 30
) -> dict:
    info = fetch_repo_info(owner, repo, token)
    commits = fetch_recent_commits(owner, repo, token, since_days=since_days)
    releases = fetch_recent_releases(owner, repo, token)
    return {
        "repo": info,
        "commits": commits,
        "releases": releases,
        "since_days": since_days,
    }
