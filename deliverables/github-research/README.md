# Deliverable — GitHub AI Research Dashboard

> Purpose: Streamlit dashboard that searches GitHub for trending AI repositories, scores them by tier (S/A/B/C), and generates a weekly digest report.
> Owner Agent: Research Team (Scout → Analyst → Curator → Reporter)
> Status: active

## Credentials Required

| Credential | Required | Effect |
|---|---|---|
| `GITHUB_TOKEN` or `RESEARCH_GITHUB_TOKEN` | **Recommended** (optional) | Without token: 60 requests/hour. With token: 5,000 requests/hour |

The app works without a token, but you'll hit rate limits quickly when scanning multiple topics.

---

## Setup

### 1. Get a GitHub Personal Access Token (PAT)

1. Go to [github.com/settings/tokens](https://github.com/settings/tokens)
2. **Generate new token (classic)**
3. Scopes needed: **`public_repo`** (read-only access to public repos)
4. Copy the token — it won't be shown again

### 2. Set the token

**Option A — env var:**
```bash
export GITHUB_TOKEN=ghp_xxxxxxxxxxxx
```

**Option B — Streamlit secrets** (for the dashboard):
```toml
# .streamlit/secrets.toml
GITHUB_TOKEN = "ghp_xxxxxxxxxxxx"
```

**Option C — enter in the dashboard sidebar**
No setup needed — just paste the token in the sidebar when the app is running.

---

## Run

### Streamlit dashboard
```bash
pip install -r ../../requirements-research.txt
streamlit run streamlit_research_app.py
```

### CLI (full weekly report)
```bash
python ../../scripts/github_research/main.py --output report.md
```

### CLI (daily S-tier alert only)
```bash
python ../../scripts/github_research/daily_alert.py
```

---

## What you get

- **Tier badges** — S / A / B / C scored by stars, activity, growth, community
- **Stars histogram** and **language pie chart**
- **Top-10 table** across 15 AI topics
- **Downloadable markdown report**
- **GitHub Actions** — auto-runs daily (S-tier alert) + weekly (full digest), commits report back to `process/research/`

---

## No token? No problem

The app degrades gracefully — it searches fewer topics per run and adds a 1.2s delay between requests to stay within the 60 req/hour unauthenticated limit.
