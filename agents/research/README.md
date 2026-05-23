# GitHub AI Research Department

A four-agent team that continuously scans GitHub for emerging AI tools, ranks them, and delivers structured intelligence reports to AIStudio.

## Team Structure

```
Scout
  Searches GitHub for trending AI repos by topic
    |
    v
Analyst
  Scores each repo on stars, activity, growth, community
    |
    v
Curator
  Deduplicates, categorises, and builds the knowledge taxonomy
    |
    v
Reporter
  Generates weekly markdown digest + Streamlit dashboard
```

## Agents

| Agent | File | Primary tool | Output |
|-------|------|-------------|--------|
| Scout | `scout.md` | GitHub Search API | Raw repo list per topic |
| Analyst | `analyst.md` | Scoring engine | Ranked `RepoScore` objects |
| Curator | `curator.md` | Dedup + taxonomy | Categorised shortlist |
| Reporter | `reporter.md` | Markdown + Streamlit | Weekly digest + dashboard |

## Topics monitored

`llm` · `large-language-model` · `generative-ai` · `ai-agents` · `rag` ·
`retrieval-augmented-generation` · `prompt-engineering` · `fine-tuning` ·
`multimodal` · `diffusion-model` · `transformer` · `langchain` ·
`llamaindex` · `vector-database` · `embeddings`

## Quick start

```bash
pip install -r requirements-research.txt
export GITHUB_TOKEN=ghp_...          # optional — raises rate limit 60 -> 5000 req/h
python scripts/github_research/main.py --topics llm rag ai-agents --min-stars 200
streamlit run deliverables/github-research/streamlit_research_app.py
```

## Cadence

| Run | Trigger | Output |
|-----|---------|--------|
| Daily | Cron 07:00 UTC | Top-10 alert if any Tier-S repo is new |
| Weekly | Monday 08:00 UTC | Full digest markdown committed to `process/research/` |
| On-demand | `python main.py` | Immediate report in working dir |
