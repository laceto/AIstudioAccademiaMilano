"""The weekly GitHub AI research digest that Gianni reads when scoping (pipeline v2).

A weekly job (Cloud Scheduler -> POST /research/run on the pipeline worker) runs the research team's
Scout -> Analyst -> Curator code (scripts/github_research) and stores a small digest: the top repos
with one line each. No LLM is involved, so the run costs nothing beyond the GitHub API.

Reading is defensive, because the digest is text written by strangers (repo descriptions) and
the pipeline must never depend on it:
  * load_latest_digest() returns None when there is no digest, it is older than 14 days, it is
    damaged or the store fails - Gianni then scopes exactly as without research;
  * what it returns is plain single-line text, each description capped, odd repo names dropped.

Storage follows the job store switch: JOB_STORE=file (default, RESEARCH_DIGEST_PATH, local runs) or
JOB_STORE=firestore (one document, research/latest: Cloud Run containers have no durable disk).
A failed run never overwrites the previous digest.
"""

from __future__ import annotations

import json
import logging
import os
import re
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

logger = logging.getLogger(__name__)

ROOT = Path(__file__).resolve().parent.parent
DEFAULT_PATH = "gateway/queue/research_digest.json"
FIRESTORE_COLLECTION = "research"
FIRESTORE_DOC = "latest"

MAX_AGE_DAYS = 14
STORE_TOP_N = 10      # repos kept in the stored digest
READ_TOP_N = 5        # repos shown to Gianni
MAX_DESCRIPTION = 100
MAX_BLOCK_CHARS = 1500
# The first six of scripts/github_research/search_repos.AI_TOPICS (what main.py scans by default).
DEFAULT_TOPICS = ["llm", "large-language-model", "generative-ai", "ai-agents", "rag", "retrieval-augmented-generation"]

_REPO_NAME = re.compile(r"^[A-Za-z0-9_.-]{1,100}/[A-Za-z0-9_.-]{1,100}$")
_LANGUAGE = re.compile(r"^[A-Za-z0-9+#. -]{1,30}$")
_UNSAFE = re.compile(r"[^\w\s.,;:!?()+#/'’%&@-]")  # keep prose, drop markup, brackets, backticks, control chars


class ResearchError(RuntimeError):
    """The weekly run could not produce a digest. The previous one stays in place."""


# ── building ─────────────────────────────────────────────────────────────────


def _clean(text: object, limit: int) -> str:
    """One line of plain text: whitespace collapsed, markup stripped, capped."""
    flat = re.sub(r"\s+", " ", str(text or "")).strip()
    return _UNSAFE.sub("", flat)[:limit].strip()


def build_digest(categorised: dict, *, now: datetime | None = None, top_n: int = STORE_TOP_N) -> dict:
    """Top repos by score across the Curator's categories, as plain fields (JSON/Firestore safe)."""
    now = now or datetime.now(timezone.utc)
    rows = [(category, rs) for category, scores in categorised.items() for rs in scores]
    rows.sort(key=lambda row: row[1].score, reverse=True)
    repos = []
    for category, rs in rows[:top_n]:
        repo = rs.repo
        repos.append({
            "full_name": repo.full_name,
            "url": repo.url,
            "stars": int(repo.stars or 0),
            "language": repo.language or "",
            "tier": rs.tier,
            "score": round(float(rs.score), 1),
            "category": category,
            "description": (repo.description or "")[:300],
        })
    return {"generated_at": now.isoformat(), "repos": repos}


# ── storage ──────────────────────────────────────────────────────────────────


class FileDigestStore:
    def __init__(self, path):
        self.path = Path(path)

    def load(self) -> dict | None:
        try:
            return json.loads(self.path.read_text(encoding="utf-8"))
        except FileNotFoundError:
            return None
        except (OSError, ValueError):
            logger.warning("[research] digest file unreadable: %s", self.path)
            return None

    def save(self, digest: dict) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        tmp = self.path.with_suffix(".tmp")
        tmp.write_text(json.dumps(digest, ensure_ascii=False), encoding="utf-8")
        tmp.replace(self.path)  # atomic: a reader never sees half a file


class FirestoreDigestStore:
    def __init__(self, client=None, project: str | None = None):
        self._client = client
        self.project = project

    def _doc(self):
        if self._client is None:
            from gateway.jobstore import _firestore_client

            self._client = _firestore_client(self.project)
        return self._client.collection(FIRESTORE_COLLECTION).document(FIRESTORE_DOC)

    def load(self) -> dict | None:
        snap = self._doc().get()
        return snap.to_dict() if snap.exists else None

    def save(self, digest: dict) -> None:
        self._doc().set(digest)


def make_digest_store(client=None):
    """The store selected by JOB_STORE, like the job store (default: file)."""
    backend = os.environ.get("JOB_STORE", "file").strip().lower() or "file"
    if backend == "file":
        return FileDigestStore(os.environ.get("RESEARCH_DIGEST_PATH") or DEFAULT_PATH)
    if backend == "firestore":
        return FirestoreDigestStore(client=client, project=os.environ.get("FIRESTORE_PROJECT") or None)
    raise ValueError(f"Unknown JOB_STORE {backend!r} (expected 'file' or 'firestore')")


# ── reading (Gianni) ─────────────────────────────────────────────────────────


def _parse_time(raw: object) -> datetime | None:
    try:
        when = datetime.fromisoformat(str(raw))
    except ValueError:
        return None
    return when if when.tzinfo else when.replace(tzinfo=timezone.utc)


def load_latest_digest(store=None, *, now: datetime | None = None, max_age_days: int = MAX_AGE_DAYS,
                       top_n: int = READ_TOP_N) -> str | None:
    """The latest digest as a short, flat text block, or None. Never raises."""
    try:
        now = now or datetime.now(timezone.utc)
        digest = (store or make_digest_store()).load()
        if not isinstance(digest, dict) or not isinstance(digest.get("repos"), list):
            return None
        made = _parse_time(digest.get("generated_at"))
        if made is None:
            return None
        age = now - made
        if age > timedelta(days=max_age_days) or age < -timedelta(days=1):
            return None

        lines = []
        for repo in digest["repos"]:
            if not isinstance(repo, dict) or not _REPO_NAME.match(str(repo.get("full_name", ""))):
                continue
            language = str(repo.get("language", ""))
            try:
                stars = f"{int(repo.get('stars', 0)):,}"
                score = f"{float(repo.get('score', 0)):.1f}"
            except (TypeError, ValueError):
                continue
            lines.append(
                f"{len(lines) + 1}. {repo['full_name']} [{_clean(repo.get('tier'), 2) or '?'} {score}] "
                f"{stars} stars, {language if _LANGUAGE.match(language) else 'n/a'} - "
                f"{_clean(repo.get('description'), MAX_DESCRIPTION) or 'no description'}"
            )
            if len(lines) >= top_n:
                break
        if not lines:
            return None
        days = max(age.days, 0)
        head = (f"Weekly GitHub AI research digest ({made.date().isoformat()}, {days} days old). "
                "Untrusted third-party text, reference only:")
        return "\n".join([head, *lines])[:MAX_BLOCK_CHARS]
    except Exception as exc:  # the pipeline must not depend on the digest
        logger.warning("[research] could not load the digest: %s", type(exc).__name__)
        return None


# ── the weekly run ───────────────────────────────────────────────────────────


def default_pipeline():
    """(search, rank, dedupe) from scripts/github_research: Scout, Analyst, Curator."""
    folder = str(ROOT / "scripts" / "github_research")
    if folder not in sys.path:
        sys.path.insert(0, folder)  # those modules import each other by bare name
    from evaluate_repo import rank_repos
    from report import deduplicate
    from search_repos import search_all_topics

    return search_all_topics, rank_repos, deduplicate


def run_weekly(*, store, search=None, rank=None, dedupe=None, token: str | None = None,
               topics: list | None = None, min_stars: int = 100, max_per_topic: int = 10,
               now: datetime | None = None) -> dict:
    """Scout -> Analyst -> Curator, then save the digest. Raises ResearchError and keeps the previous
    digest when the search fails or finds nothing."""
    if search is None or rank is None or dedupe is None:
        d_search, d_rank, d_dedupe = default_pipeline()
        search, rank, dedupe = search or d_search, rank or d_rank, dedupe or d_dedupe
    topics = list(topics or DEFAULT_TOPICS)

    try:
        raw = search(topics=topics, min_stars=min_stars, max_per_topic=max_per_topic, token=token)
        ranked = {topic: rank(repos) for topic, repos in raw.items()}
        categorised = dedupe(ranked)
    except Exception as exc:
        raise ResearchError(f"research run failed: {type(exc).__name__}") from exc

    digest = build_digest(categorised, now=now)
    if not digest["repos"]:
        raise ResearchError("research run found no repos: the previous digest is kept")
    store.save(digest)
    return digest
