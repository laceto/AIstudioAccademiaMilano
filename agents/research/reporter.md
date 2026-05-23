# Reporter Agent

**Role:** Digest Generation & Dashboard  
**Reports to:** Research Department  
**Script:** `scripts/github_research/report.py` + `deliverables/github-research/streamlit_research_app.py`

## Responsibility

Reporter takes the curated, categorised shortlist from Curator and produces two outputs:

1. **Markdown digest** — committed to `process/research/YYYY-MM-DD_weekly.md`
2. **Streamlit dashboard** — live interactive view with filtering, tier badges, and export

## Digest structure

```
# GitHub AI Research Report — YYYY-MM-DD
## Top 10 Picks          <- global ranking across all categories
## Foundation Models     <- top 5 per category
## Agentic Systems
## RAG & Search
## Generation
## Training & Tuning
```

## Dashboard features

- Sidebar: topic filter, min-stars slider, GITHUB_TOKEN input
- Main table: sortable by score / stars / activity, tier badge colour coding
- Charts: stars distribution histogram, language breakdown pie
- Export: download full report as markdown

## Alert rule

If any repo scores Tier-S AND was created in the last 30 days, Reporter flags it as **New Discovery** in the digest header and logs it to `process/audit/` as a learning event.
