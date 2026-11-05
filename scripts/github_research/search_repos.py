import time
from dataclasses import dataclass
from typing import Optional
import requests

GITHUB_API = "https://api.github.com"
_BASE_HEADERS = {
    "Accept": "application/vnd.github+json",
    "X-GitHub-Api-Version": "2022-11-28",
}

AI_TOPICS = [
    "llm",
    "large-language-model",
    "generative-ai",
    "ai-agents",
    "rag",
    "retrieval-augmented-generation",
    "prompt-engineering",
    "fine-tuning",
    "multimodal",
    "diffusion-model",
    "transformer",
    "langchain",
    "llamaindex",
    "vector-database",
    "embeddings",
]


@dataclass
class Repo:
    name: str
    full_name: str
    description: str
    stars: int
    forks: int
    language: str
    topics: list
    url: str
    created_at: str
    updated_at: str
    pushed_at: str
    trending_stars: int = 0   # stars gained in the trending period (0 = not on github.com/trending)
    trending_since: str = ""  # "daily" | "weekly" | "monthly" when trending


def _headers(token: Optional[str] = None) -> dict:
    h = _BASE_HEADERS.copy()
    if token:
        h["Authorization"] = f"Bearer {token}"
    return h


def search_repos(
    topic: str,
    min_stars: int = 100,
    max_results: int = 20,
    token: Optional[str] = None,
) -> list:
    params = {
        "q": f"topic:{topic} stars:>{min_stars}",
        "sort": "stars",
        "order": "desc",
        "per_page": min(max_results, 100),
    }
    resp = requests.get(
        f"{GITHUB_API}/search/repositories",
        headers=_headers(token),
        params=params,
        timeout=15,
    )
    resp.raise_for_status()
    return [
        Repo(
            name=r["name"],
            full_name=r["full_name"],
            description=r.get("description") or "",
            stars=r["stargazers_count"],
            forks=r["forks_count"],
            language=r.get("language") or "Unknown",
            topics=r.get("topics", []),
            url=r["html_url"],
            created_at=r["created_at"],
            updated_at=r["updated_at"],
            pushed_at=r["pushed_at"],
        )
        for r in resp.json().get("items", [])
    ]


def search_all_topics(
    topics: list = None,
    min_stars: int = 100,
    max_per_topic: int = 10,
    token: Optional[str] = None,
    delay: float = 1.2,
    trending: Optional[str] = "weekly",
    trending_language: Optional[str] = None,
) -> dict:
    """{topic: [Repo]} from the topic search, plus a "trending" bucket with the AI repos on
    github.com/trending for the period (trending=None switches it off). Topic hits that are also
    trending carry the trending mark too, so the mark survives the Curator's deduplication."""
    if topics is None:
        topics = AI_TOPICS
    results = {}
    for topic in topics:
        try:
            results[topic] = search_repos(
                topic, min_stars=min_stars, max_results=max_per_topic, token=token
            )
        except Exception as e:
            print(f"  [Scout] Error on topic '{topic}': {e}")
            results[topic] = []
        time.sleep(delay)
    if not trending:
        return results

    import trending as trending_page  # lazy: trending imports this module

    try:
        hot = trending_page.fetch_trending(trending, language=trending_language, token=token)
    except Exception as e:
        print(f"  [Scout] Error on trending: {e}")
        hot = []
    results["trending"] = hot
    gained = {r.full_name: r for r in hot}
    for topic, repos in results.items():
        if topic == "trending":
            continue
        for repo in repos:
            if repo.full_name in gained:
                repo.trending_stars = gained[repo.full_name].trending_stars
                repo.trending_since = gained[repo.full_name].trending_since
    return results
