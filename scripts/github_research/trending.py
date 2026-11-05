"""GitHub trending for the research Scout.

GitHub has no API for trending, so this reads the public page github.com/trending (all languages, or
one language) and keeps the repos that look like AI by name and description. Each kept repo is then
described by the REST API (topics, creation date, last push), so the Analyst scores it like any other.

Everything here is best effort: the page is HTML that GitHub can change at any time. A page that
cannot be fetched or parsed gives an empty list, never an error, and the topic search runs as before.
The token goes only to api.github.com, never to the HTML page.
"""

from __future__ import annotations

import html
import re
from typing import Callable, Optional

import requests

from search_repos import GITHUB_API, Repo, _headers

TRENDING_URL = "https://github.com/trending"
PERIODS = ("daily", "weekly", "monthly")
PAGE_HEADERS = {"User-Agent": "aistudio-research-scout", "Accept": "text/html"}

_ARTICLE = re.compile(r'<article\b[^>]*class="[^"]*\bBox-row\b[^"]*"[^>]*>(.*?)</article>', re.S | re.I)
_NAME = re.compile(r'<h2\b[^>]*>.*?<a\b[^>]*href="/([A-Za-z0-9_.-]+)/([A-Za-z0-9_.-]+)"', re.S | re.I)
_DESC = re.compile(r'<p\b[^>]*>(.*?)</p>', re.S | re.I)
_LANG = re.compile(r'itemprop="programmingLanguage"[^>]*>(.*?)<', re.S | re.I)
_STARS = re.compile(r'href="/[^"]+/stargazers"[^>]*>(.*?)</a>', re.S | re.I)
_FORKS = re.compile(r'href="/[^"]+/forks"[^>]*>(.*?)</a>', re.S | re.I)
_GAINED = re.compile(r'([\d,]+)\s+stars?\s+(?:today|this\s+week|this\s+month)', re.I)
_TAGS = re.compile(r"<[^>]+>")

# Whole-word cues that a repo is about AI. Deliberately narrow: a false negative only means one
# trending repo is missed, a false positive puts a CSS library in the AI digest.
_AI_WORDS = re.compile(
    r"\b(ai|a\.i\.|llms?|gpts?|chatgpt|agents?|agentic|rag|langchain|langgraph|llamaindex|llama|"
    r"embeddings?|transformers?|diffusion|multimodal|fine-?tun\w*|lora|prompts?|mcp|openai|anthropic|"
    r"claude|gemini|mistral|ollama|vllm|deepseek|qwen|copilot|chatbots?|inference|neural|"
    r"machine learning|deep learning|retrieval|vector (?:db|database|store|search)|model context protocol)\b",
    re.I,
)


def _text(fragment: str) -> str:
    return re.sub(r"\s+", " ", html.unescape(_TAGS.sub(" ", fragment or ""))).strip()


def _int(fragment: str) -> int:
    digits = re.sub(r"[^\d]", "", _text(fragment))
    return int(digits) if digits else 0


def parse_trending(page: str) -> list[dict]:
    """The repos on a trending page, in page order. Rows without a repo link are skipped."""
    rows = []
    for block in _ARTICLE.findall(page or ""):
        name = _NAME.search(block)
        if not name:
            continue
        desc, lang = _DESC.search(block), _LANG.search(block)
        stars, forks, gained = _STARS.search(block), _FORKS.search(block), _GAINED.search(_text(block))
        rows.append({
            "full_name": f"{name.group(1)}/{name.group(2)}",
            "description": _text(desc.group(1)) if desc else "",
            "language": _text(lang.group(1)) if lang else "",
            "stars": _int(stars.group(1)) if stars else 0,
            "forks": _int(forks.group(1)) if forks else 0,
            "stars_gained": int(gained.group(1).replace(",", "")) if gained else 0,
        })
    return rows


def looks_ai(row: dict) -> bool:
    name = str(row.get("full_name", "")).split("/")[-1].replace("-", " ").replace("_", " ")
    return bool(_AI_WORDS.search(f"{name} {row.get('description', '')}"))


def _from_page(row: dict, since: str) -> Repo:
    owner_name = row["full_name"]
    return Repo(
        name=owner_name.split("/")[1], full_name=owner_name, description=row["description"],
        stars=row["stars"], forks=row["forks"], language=row["language"] or "Unknown", topics=[],
        url=f"https://github.com/{owner_name}", created_at="", updated_at="", pushed_at="",
        trending_stars=row["stars_gained"], trending_since=since,
    )


def _from_api(data: dict, row: dict, since: str) -> Repo:
    return Repo(
        name=data["name"], full_name=data["full_name"], description=data.get("description") or row["description"],
        stars=data["stargazers_count"], forks=data["forks_count"],
        language=data.get("language") or row["language"] or "Unknown", topics=data.get("topics", []),
        url=data["html_url"], created_at=data["created_at"], updated_at=data["updated_at"],
        pushed_at=data["pushed_at"], trending_stars=row["stars_gained"], trending_since=since,
    )


def fetch_trending(
    since: str = "weekly",
    language: Optional[str] = None,
    token: Optional[str] = None,
    ai_only: bool = True,
    get: Callable = requests.get,
) -> list:
    """AI repos trending on GitHub in the period, as Repo objects marked with trending_stars."""
    if since not in PERIODS:
        raise ValueError(f"since must be one of {PERIODS}, not {since!r}")
    url = f"{TRENDING_URL}/{language}" if language else TRENDING_URL
    try:
        resp = get(url, headers=dict(PAGE_HEADERS), params={"since": since}, timeout=15)
        resp.raise_for_status()
        rows = parse_trending(resp.text)
    except Exception as exc:
        print(f"  [Scout] Trending page unavailable ({type(exc).__name__}): skipped")
        return []

    repos = []
    for row in rows:
        if ai_only and not looks_ai(row):
            continue
        try:
            api = get(f"{GITHUB_API}/repos/{row['full_name']}", headers=_headers(token), timeout=15)
            api.raise_for_status()
            repos.append(_from_api(api.json(), row, since))
        except Exception:
            repos.append(_from_page(row, since))  # scored with what the page says
    return repos
