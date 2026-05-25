"""
UserScore — client prospecting scoring for AI Studio Accademia Milano.

Scores UserProfile objects on four dimensions:
  activity     (25%) — how actively they're building right now
  ai_signal    (30%) — how AI-native their tooling is
  incompleteness (25%) — how much studio help they need
  reachability (20%) — how contactable they are

Reachability gate: if reachability < 20, cap tier at B regardless of total.
"""

from dataclasses import dataclass
from .search_users import UserProfile

TIER_THRESHOLDS = {"S": 80, "A": 60, "B": 40}  # mirrors evaluate_repo.py

# Studio products inferred from user signals
_PRODUCT_RULES = [
    ("rag_knowledge_base",    lambda p: any(t in p.ai_signal_topics for t in ("rag", "embeddings", "vector-database", "llamaindex"))),
    ("chatbot_app",           lambda p: any(t in p.ai_signal_topics for t in ("llm", "langchain", "openai", "chatgpt", "gpt4"))),
    ("agent_deploy_streamlit",lambda p: "streamlit" in p.ai_signal_topics),
    ("static_landing_page",   lambda p: p.recent_repos_60d >= 3 and not p.has_live_url),
    ("chatbot_app",           lambda p: bool(p.ai_signal_keywords)),  # any AI keyword in bio
]


@dataclass
class UserScore:
    profile: UserProfile
    score: float
    tier: str
    signals: dict
    needs_inferred: list   # ordered list of studio product types


def _infer_needs(profile: UserProfile) -> list:
    seen = set()
    needs = []
    for product, rule in _PRODUCT_RULES:
        if rule(profile) and product not in seen:
            needs.append(product)
            seen.add(product)
    return needs


def score_user(profile: UserProfile) -> UserScore:
    # Activity: recent_repos_60d / 5 → 100 at 5+ repos in 60 days
    activity = min(profile.recent_repos_60d / 5, 1.0) * 100

    # AI signal: (topics + keywords) / 3 → 100 at 3+ signals
    ai_count = len(profile.ai_signal_topics) + len(profile.ai_signal_keywords)
    ai_signal = min(ai_count / 3, 1.0) * 100

    # Incompleteness: missing live URL and email → max studio need
    incompleteness = 100 - (int(profile.has_live_url) * 60 + int(bool(profile.email)) * 40)

    # Reachability: contactable via email, bio, location
    reachability = (
        int(bool(profile.email)) * 50
        + int(bool(profile.bio)) * 30
        + int(bool(profile.location)) * 20
    )

    total = (
        activity      * 0.25
        + ai_signal   * 0.30
        + incompleteness * 0.25
        + reachability * 0.20
    )
    total = round(total, 1)

    # Tier assignment
    if reachability < 20:
        # Unreachable users capped at B regardless of total score
        tier = "B" if total >= 40 else "C"
    else:
        tier = "C"
        for label, threshold in TIER_THRESHOLDS.items():
            if total >= threshold:
                tier = label
                break

    return UserScore(
        profile=profile,
        score=total,
        tier=tier,
        signals={
            "activity":       round(activity, 1),
            "ai_signal":      round(ai_signal, 1),
            "incompleteness": round(incompleteness, 1),
            "reachability":   round(reachability, 1),
        },
        needs_inferred=_infer_needs(profile),
    )


def rank_users(profiles: list) -> list:
    """Score and sort a list of UserProfile objects descending by score."""
    return sorted(
        [score_user(p) for p in profiles],
        key=lambda us: us.score,
        reverse=True,
    )
