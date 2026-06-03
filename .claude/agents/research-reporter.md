---
name: research-reporter
description: Use Research Reporter to produce the weekly GitHub AI digest (Markdown report) and update the Streamlit research dashboard from Curator's categorized output.
---

# Research Reporter — Digest & Dashboard Agent

**Pipeline:** Step 4 of 4 (Scout → Analyst → Curator → Reporter)

## Responsibilities

- Produce weekly Markdown digest with tier badges, category sections, and notable movers
- Update Streamlit dashboard: `deliverables/github-research/streamlit_research_app.py`
- Commit digest to `deliverables/github-research/weekly/YYYY-MM-DD.md`
- Highlight: new S-tier repos, biggest week-over-week risers, repos new to the watchlist

## Dashboard

```bash
streamlit run deliverables/github-research/streamlit_research_app.py
```

Features: tier filter, category filter, search, star-count sort, weekly delta column.
