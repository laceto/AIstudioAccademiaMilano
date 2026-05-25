---
name: contributor-scout-agent
type: agent
summary: ContributorScout is a GitHub Research Department agent that finds and scores potential studio clients among active AI-native GitHub builders.
owner: Scout
status: active
related: [github-research-department, contributor-scout-report]
citations: []
chunk_strategy: header
---

# ContributorScout Agent

> ContributorScout is a GitHub Research Department agent that finds and scores potential
> studio clients among active AI-native GitHub builders.

---

## Overview

ContributorScout extends the GitHub Research Department (Scout → Analyst → Curator →
Reporter) with a parallel user-centric pipeline. While the existing Scout agent searches
for trending AI repositories by topic, ContributorScout searches for the *people* building
those repositories — specifically Python developers with 3+ recent repos and detectable
AI-tool usage signals.

The primary use case is client prospecting: identify developers who are building AI
applications but lack a deployed product (no live URL), polished landing page, or
backend infrastructure that the studio sells. Every candidate is scored on activity,
ai_signal, incompleteness, and reachability, then ranked into tiers S/A/B/C. Unreachable
candidates (no email, bio, or location) are automatically capped at tier B.

The output is a weekly markdown shortlist (`contributor_report.md`) that Luigi reviews
before any outreach. The agent does not send emails or messages — it only surfaces leads.

---

## Architecture

```
GitHub Search API  (/search/users?q=language:python+repos:>3+followers:>5)
  |
  v
[search_users.py :: search_contributors()]
    Enriches via /users/{login} + /users/{login}/repos
    Detects AI signals: topics (llm, langchain, openai, claude-code, cursor)
                        bio keywords (built with claude, vibe coding)
  |
  v
[score_user.py :: rank_users()]
    activity (25%) + ai_signal (30%) + incompleteness (25%) + reachability (20%)
    Reachability gate: score < 20 → cap tier at B
    needs_inferred: maps signals → studio product types
  |
  v
[report_users.py :: generate_contributor_report()]
    Top 10 table + sections by inferred_need
    GDPR notice at top
  |
  v
contributor_report.md  →  Luigi reviews  →  manual outreach decision
```

---

## Components

| Name | File | Role | Output |
|------|------|------|--------|
| UserProfile | `search_users.py` | Data model for a GitHub user | Dataclass |
| search_contributors | `search_users.py` | Scout: API calls + enrichment | `[UserProfile]` |
| UserScore | `score_user.py` | Data model for a scored user | Dataclass |
| rank_users | `score_user.py` | Analyst: score + tier + needs | `[UserScore]` |
| generate_contributor_report | `report_users.py` | Reporter: markdown output | `contributor_report.md` |

The pipeline is wired into `scripts/github_research/main.py` via `--mode contributors`.
It runs independently of the repo pipeline (no shared state, no deduplication needed
since users are unique by login).

---

## Configuration

```json
{
  "DEFAULT_QUERY": "language:python repos:>3 followers:>5",
  "AI_TOOL_TOPICS": ["claude-code", "cursor", "copilot", "llm", "langchain", "openai",
                     "rag", "embeddings", "vector-database", "streamlit"],
  "REACHABILITY_GATE": 20,
  "MAX_RESULTS_DEFAULT": 30,
  "RATE_LIMIT_DELAY_SEC": 1.2,
  "README_SCAN_DEFAULT": false
}
```

Set `GITHUB_TOKEN` or `RESEARCH_GITHUB_TOKEN` env var. Without a token, the agent is
limited to 10 req/min on search and 60 req/h total — enough for ~10 users per run.

---

## Quick Start

```bash
export GITHUB_TOKEN=ghp_...

# Run contributor scout only
python scripts/github_research/main.py --mode contributors

# Run both repo research + contributor scout
python scripts/github_research/main.py --mode both

# Include README scanning (slower, more accurate)
python scripts/github_research/main.py --mode contributors --scan-readmes
```

Expected output: `contributor_report.md` with Top 10 table and sections per inferred need.

---

## Triggers / Cadence

| When | Trigger | Output |
|------|---------|--------|
| Weekly Monday 08:00 UTC | Cron — ISS-023 pending | `process/research/contributor_YYYY-MM-DD.md` |
| On-demand | CLI `--mode contributors` | `contributor_report.md` in working dir |

---

## Citations

<!-- ISS-006 will populate this section. -->

---

## Notes

- `needs_inferred` is rule-based, not ML — expect ~30% false positives. Luigi's review is
  the quality gate, not the model.
- GDPR: EU contacts need consent mechanism before any automated outreach. Build before
  wiring to email send.
- ISS-023 tracks the cron extension. Until then, run on-demand weekly.
