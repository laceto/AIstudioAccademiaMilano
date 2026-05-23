import math
from dataclasses import dataclass
from datetime import datetime, timezone
from search_repos import Repo

WEIGHTS = {"stars": 0.30, "activity": 0.25, "growth": 0.25, "community": 0.20}
TIERS = [(80, "S"), (60, "A"), (40, "B"), (0, "C")]


@dataclass
class RepoScore:
    repo: Repo
    score: float
    tier: str
    signals: dict


def _tier(score: float) -> str:
    for threshold, label in TIERS:
        if score >= threshold:
            return label
    return "C"


def score_repo(repo: Repo) -> RepoScore:
    now = datetime.now(timezone.utc)

    stars_score = min(math.log10(max(repo.stars, 1)) / math.log10(50_000), 1.0) * 100

    try:
        pushed = datetime.fromisoformat(repo.pushed_at.replace("Z", "+00:00"))
        activity_score = max(0.0, 100.0 - (now - pushed).days * 2)
    except Exception:
        activity_score = 0.0

    try:
        created = datetime.fromisoformat(repo.created_at.replace("Z", "+00:00"))
        age_days = max((now - created).days, 1)
        growth_score = min(repo.stars / age_days * 10, 100.0)
    except Exception:
        growth_score = 0.0

    community_score = min(repo.forks / max(repo.stars, 1) * 200, 100.0)

    total = (
        WEIGHTS["stars"] * stars_score
        + WEIGHTS["activity"] * activity_score
        + WEIGHTS["growth"] * growth_score
        + WEIGHTS["community"] * community_score
    )

    return RepoScore(
        repo=repo,
        score=round(total, 1),
        tier=_tier(total),
        signals={
            "stars": round(stars_score, 1),
            "activity": round(activity_score, 1),
            "growth": round(growth_score, 1),
            "community": round(community_score, 1),
        },
    )


def rank_repos(repos: list) -> list:
    return sorted([score_repo(r) for r in repos], key=lambda x: x.score, reverse=True)
