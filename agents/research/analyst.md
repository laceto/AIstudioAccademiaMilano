# Analyst Agent

**Role:** Repo Evaluation & Scoring  
**Reports to:** Research Department  
**Script:** `scripts/github_research/evaluate_repo.py`

## Responsibility

Analyst receives the raw repo list from Scout and produces a ranked score for each repo using a weighted actuarial model. Output is a `RepoScore` with a tier (S/A/B/C) and a breakdown of signal components.

## Scoring Model

| Signal | Weight | Method |
|--------|--------|--------|
| Stars | 30% | log10 scale, capped at 50k |
| Activity | 25% | days since last push (-2/day, floor 0) |
| Growth | 25% | stars per day since creation |
| Community | 20% | forks/stars ratio (0.5 = 100) |

**Score range:** 0–100  
**Tiers:** S (>=80) · A (>=60) · B (>=40) · C (<40)

## Output

```python
list[RepoScore]  # sorted descending by score
```

## Actuarial note

All scores are continuous numerical values — Analyst never produces vague qualitative labels. Risk/opportunity decisions downstream are based on the score distribution, not gut feel.
