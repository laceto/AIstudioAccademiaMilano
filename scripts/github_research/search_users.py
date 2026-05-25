"""
ContributorScout — user search for AI Studio Accademia Milano.

Finds GitHub users actively building AI apps who likely need studio products.
Primary use: client prospecting (not recruitment or competitive intelligence).

Default: bio + repo topics only (fast, ~2 calls/user).
With --scan-readmes: also fetches repo READMEs (~10 calls/user, requires token).
"""

import time
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Optional

import requests

GITHUB_API = "https://api.github.com"
_BASE_HEADERS = {
    "Accept": "application/vnd.github+json",
    "X-GitHub-Api-Version": "2022-11-28",
}

AI_TOOL_TOPICS = {
    "claude-code", "cursor", "copilot", "ai-generated", "vibe-coding",
    "llm", "langchain", "openai", "chatgpt", "gpt4", "ai-agent",
    "rag", "embeddings", "vector-database", "langchain", "llamaindex",
    "streamlit", "fastapi",
}

AI_KEYWORDS = [
    "built with claude",
    "co-authored-by: claude",
    "made with cursor",
    "github copilot",
    "vibe coding",
    "vibe-coded",
    "ai coding",
]

# Default search: active Python builders with some followers (avoids bots)
DEFAULT_QUERY = "language:python repos:>3 followers:>5"


@dataclass
class UserProfile:
    login: str
    name: str
    bio: str
    followers: int
    public_repos: int
    recent_repos_60d: int            # repos created in last 60 days
    ai_signal_topics: list           # repo topics matching AI_TOOL_TOPICS
    ai_signal_keywords: list         # keywords found in bio
    top_languages: list              # primary languages across recent repos
    has_live_url: bool               # any repo has a homepage URL
    email: str
    location: str
    created_at: str
    url: str


def _headers(token: Optional[str] = None) -> dict:
    h = _BASE_HEADERS.copy()
    if token:
        h["Authorization"] = f"Bearer {token}"
    return h


def _enrich_user(login: str, token: Optional[str], scan_readmes: bool = False) -> Optional[UserProfile]:
    """Fetch /users/{login} and /users/{login}/repos to build a UserProfile."""
    hdrs = _headers(token)
    try:
        profile_resp = requests.get(f"{GITHUB_API}/users/{login}", headers=hdrs, timeout=10)
        profile_resp.raise_for_status()
        p = profile_resp.json()

        repos_resp = requests.get(
            f"{GITHUB_API}/users/{login}/repos",
            headers=hdrs,
            params={"sort": "created", "direction": "desc", "per_page": 20},
            timeout=10,
        )
        repos_resp.raise_for_status()
        repos = repos_resp.json()
    except Exception as e:
        print(f"  [ContributorScout] Error enriching {login}: {e}")
        return None

    cutoff = datetime.now(timezone.utc) - timedelta(days=60)
    recent_repos = [
        r for r in repos
        if datetime.fromisoformat(r["created_at"].replace("Z", "+00:00")) > cutoff
    ]

    all_topics: set = set()
    languages: list = []
    has_live_url = False

    for repo in repos[:10]:
        all_topics.update(repo.get("topics") or [])
        lang = repo.get("language")
        if lang and lang not in languages:
            languages.append(lang)
        if repo.get("homepage"):
            has_live_url = True

    ai_signal_topics = sorted(all_topics & AI_TOOL_TOPICS)
    bio = p.get("bio") or ""
    ai_signal_keywords = [kw for kw in AI_KEYWORDS if kw.lower() in bio.lower()]

    if scan_readmes and token:
        for repo in repos[:5]:
            try:
                rm_resp = requests.get(
                    f"{GITHUB_API}/repos/{login}/{repo['name']}/readme",
                    headers={**hdrs, "Accept": "application/vnd.github.raw"},
                    timeout=8,
                )
                if rm_resp.ok:
                    content = rm_resp.text.lower()
                    for kw in AI_KEYWORDS:
                        if kw in content and kw not in ai_signal_keywords:
                            ai_signal_keywords.append(kw)
                time.sleep(0.3)
            except Exception:
                pass

    return UserProfile(
        login=p["login"],
        name=p.get("name") or "",
        bio=bio,
        followers=p.get("followers", 0),
        public_repos=p.get("public_repos", 0),
        recent_repos_60d=len(recent_repos),
        ai_signal_topics=ai_signal_topics,
        ai_signal_keywords=ai_signal_keywords,
        top_languages=languages[:5],
        has_live_url=has_live_url,
        email=p.get("email") or "",
        location=p.get("location") or "",
        created_at=p.get("created_at", ""),
        url=p.get("html_url", f"https://github.com/{login}"),
    )


def search_contributors(
    query: str = DEFAULT_QUERY,
    token: Optional[str] = None,
    max_results: int = 30,
    scan_readmes: bool = False,
    delay: float = 1.2,
) -> list:
    """
    Search GitHub for users matching query, then enrich each profile.

    Returns a list of UserProfile objects. Requires a token for meaningful
    results (unauthenticated: 10 req/min search, 60 req/h total).
    """
    if not token:
        print("  [ContributorScout] No token — rate limited to 60 req/h. Results may be sparse.")

    params = {
        "q": query,
        "sort": "repositories",
        "order": "desc",
        "per_page": min(max_results, 30),
    }
    try:
        resp = requests.get(
            f"{GITHUB_API}/search/users",
            headers=_headers(token),
            params=params,
            timeout=15,
        )
        resp.raise_for_status()
        items = resp.json().get("items", [])
    except Exception as e:
        print(f"  [ContributorScout] Search failed: {e}")
        return []

    profiles = []
    for item in items[:max_results]:
        login = item["login"]
        profile = _enrich_user(login, token, scan_readmes=scan_readmes)
        if profile:
            profiles.append(profile)
        time.sleep(delay)

    return profiles
