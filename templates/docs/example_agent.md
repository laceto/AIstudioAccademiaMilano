---
name: contributor-scout
type: agent
summary: ContributorScout searches GitHub for users actively building AI apps and scores them as potential studio clients using a four-dimension prospecting model.
owner: Scout
status: active
related: [contributor-scout-report, github-research-department]
citations: []
chunk_strategy: header
---

# ContributorScout

> ContributorScout searches GitHub for users actively building AI apps and scores them as
> potential studio clients using a four-dimension prospecting model.

---

## Overview

ContributorScout is a client prospecting agent in the GitHub Research Department. It scans
GitHub for Python developers who are actively creating new repositories and show AI-native
tooling signals — topics like `llm`, `langchain`, `openai`, or keywords like "built with
claude" in their bio. The goal is not to recruit contributors or monitor competitors, but
to find people who are already building AI applications and likely need studio products:
a landing page, a chatbot app, a RAG knowledge base, or a Streamlit deployment.

Each user is scored on four dimensions: activity (how many repos they created in the last
60 days), ai_signal (how many AI-tool topics and keywords they match), incompleteness
(whether they lack a live URL or public email — gaps the studio can fill), and reachability
(whether Luigi can actually contact them via email, bio, or location). A reachability gate
caps unreachable users at tier B regardless of their total score.

The weekly output is `process/research/contributor_report.md` — a markdown shortlist of
top candidates grouped by inferred studio need. Luigi reviews this before any outreach.
GDPR applies to EU-based contacts; no automated email is sent without manual approval.

---

## Architecture

```
GitHub Search API  (/search/users)
  |
  v
[search_users.py]  Enriches each login via /users/{login} + /users/{login}/repos
  |
  v
[score_user.py]    Scores on activity, ai_signal, incompleteness, reachability
  |
  v
[report_users.py]  Generates markdown: Top 10 table + sections by inferred need
  |
  v
contributor_report.md  (reviewed by Luigi before outreach)
```

---

## Components

| Name | Role | Input | Output |
|------|------|-------|--------|
| `search_users.py` | Scout | GitHub Search API query | List of `UserProfile` objects |
| `score_user.py` | Analyst | `UserProfile` list | List of `UserScore` objects, sorted desc |
| `report_users.py` | Reporter | `UserScore` list | `contributor_report.md` markdown |

`search_users.py` calls `/search/users` with the default query
`language:python repos:>3 followers:>5`, then enriches each result with two more API
calls per user (profile + repos). README scanning is opt-in via `--scan-readmes`.

`score_user.py` applies a weighted formula and a reachability gate. `needs_inferred`
maps user signals to studio product types using simple rules: a user with `rag` or
`embeddings` topics maps to `rag_knowledge_base`; one with 3+ recent repos and no live
URL maps to `static_landing_page`.

`report_users.py` mirrors the style of the existing `report.py` for repos: a Top 10
table with tier, score, signals, and contact vector, then one section per inferred need.

---

## Configuration

```json
{
  "DEFAULT_QUERY": "language:python repos:>3 followers:>5",
  "AI_TOOL_TOPICS": ["claude-code", "cursor", "copilot", "llm", "langchain", "openai"],
  "AI_KEYWORDS": ["built with claude", "co-authored-by: claude", "vibe coding"],
  "TIER_THRESHOLDS": {"S": 80, "A": 60, "B": 40},
  "REACHABILITY_GATE": 20
}
```

`DEFAULT_QUERY`: removes `created:>2024-01-01` (which filters account creation date, not
activity) — activity is measured post-enrichment via `recent_repos_60d`.

`REACHABILITY_GATE`: users scoring below 20 on reachability (no email, no bio, no
location) are capped at tier B regardless of total score — they are unusable as leads.

Token required for useful results: set `GITHUB_TOKEN` or `RESEARCH_GITHUB_TOKEN` env var.

---

## Quick Start

```bash
# Standalone contributor scan (token strongly recommended)
export GITHUB_TOKEN=ghp_...
python scripts/github_research/main.py --mode contributors --max-results 30

# With README scanning (slower, more accurate AI signals, needs token)
python scripts/github_research/main.py --mode contributors --scan-readmes

# Both repo research + contributor scan in one run
python scripts/github_research/main.py --mode both
```

Outputs `contributor_report.md` in the working directory. The weekly cron (ISS-023)
commits it to `process/research/contributor_YYYY-MM-DD.md`.

---

## Triggers / Cadence

| When | Trigger | Output |
|------|---------|--------|
| Weekly (Monday 08:00 UTC) | Cron (ISS-023, pending) | `process/research/contributor_YYYY-MM-DD.md` |
| On-demand | `main.py --mode contributors` | `contributor_report.md` in working dir |

---

## Citations

<!-- ISS-006: source citation system will populate this section automatically. -->

---

## Notes

- Rate limit math: 30 users × 2 calls = 60 calls base. With `--scan-readmes`: +150 calls.
  Authenticated (5000 req/h): fine. Unauthenticated (60 req/h): max ~10 users without flag.
- GDPR: collecting public profile emails is permitted by GitHub ToS, but outreach to EU
  contacts requires a consent mechanism. Build before automating any email send.
- `needs_inferred` is rule-based, not ML. Expect ~30% false positive rate on first runs.
  Luigi's review before outreach is the quality gate, not the scoring model.
