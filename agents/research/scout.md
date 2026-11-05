# Scout Agent

**Role:** GitHub Discovery  
**Reports to:** Research Department  
**Script:** `scripts/github_research/search_repos.py` (+ `trending.py` for github.com/trending)

## Responsibility

Scout owns the top of the research funnel. It queries the GitHub Search API for repositories matching a curated list of AI topics, applies a minimum star threshold to filter noise, and returns a raw list of `Repo` objects for downstream processing.

**Trending (049).** Scout also reads github.com/trending (default `weekly`, `--trending off` to skip)
and keeps only repos that look like AI by name/description. Each kept repo is described by the
REST API (topics, dates) and carries `trending_stars` (stars gained in the period). They land in a
`trending` bucket; topic hits that are also trending get the same mark. The page is HTML with no
API: if it fails or changes layout, Scout logs it and returns the topic search alone.

## Inputs

| Parameter | Default | Description |
|-----------|---------|-------------|
| `topics` | `AI_TOPICS` (15 topics) | GitHub topic slugs to search |
| `min_stars` | 100 | Minimum star count to include |
| `max_per_topic` | 10 | Max repos fetched per topic |
| `token` | `$GITHUB_TOKEN` | Optional PAT for higher rate limits |

## Output

```python
dict[str, list[Repo]]  # topic -> list of repos
```

## Constraints

- Respects GitHub rate limits: 60 req/h unauthenticated, 5000 req/h with PAT
- Adds 1-second delay between topic requests
- Never stores credentials — reads `GITHUB_TOKEN` from env only
- Search is read-only — Scout never writes to GitHub

## Escalation

If a search returns 0 results or an HTTP error, Scout logs the failure and continues to the next topic. It does NOT abort the run.
