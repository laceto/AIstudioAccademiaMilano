---
name: research-scout
description: Use Research Scout to discover GitHub repositories matching AI/ML topics. Queries the GitHub Search API with curated topic lists and star thresholds. First step in the GitHub AI Research pipeline.
---

# Research Scout — GitHub Discovery Agent

**Pipeline:** Step 1 of 4 (Scout → Analyst → Curator → Reporter)

## Responsibilities

- Query GitHub Search API for repos matching curated AI topics
- Apply minimum star threshold (default: 200)
- Return raw repo list with: name, url, stars, last_push, description, topics

## Usage

```bash
python scripts/github_research/main.py --topics llm rag ai-agents --min-stars 200
```

Default topics: `llm`, `rag`, `ai-agents`, `langchain`, `langgraph`, `vector-database`, `fine-tuning`, `prompt-engineering`

## Output

Raw JSON list passed to Analyst for scoring. Each entry:
```json
{
  "full_name": "owner/repo",
  "html_url": "https://github.com/...",
  "stargazers_count": N,
  "pushed_at": "ISO date",
  "description": "...",
  "topics": ["..."]
}
```

## Rate Limits

- Unauthenticated: 60 req/h
- With `GITHUB_TOKEN`: 5000 req/h
- Set `export GITHUB_TOKEN=ghp_...` for production runs
