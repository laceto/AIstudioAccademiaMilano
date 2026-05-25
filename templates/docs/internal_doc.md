---
name: <slug>
type: agent
# type options: agent | skill | howto | pipeline | reference
summary: <One sentence — what this does and why it exists. Used as the semantic anchor for RAG retrieval.>
owner: <AgentName>
status: active
# status options: active | draft | deprecated
related: []
# related: [other-doc-slug, another-slug]  — links to related docs
citations: []
# citations: [] — reserved for ISS-006 source citation system (leave empty for now)
chunk_strategy: header
# chunk_strategy: header — reserved hint for future semantic chunker; no current effect.
# The RAG system (scripts/rag/embed_repo.py) chunks at 400 words / 50-word overlap.
# Design sections to be 300–600 words for clean single-chunk retrieval.
---

# <Title>

> <Repeat the `summary` field here as a blockquote. This ensures the semantic anchor appears
> in the first chunk regardless of frontmatter handling.>

---

## Overview

<!--
TARGET: ≈150–200 words. Narrative prose — this section drives FAISS semantic retrieval.

Write 2–3 paragraphs:
1. What this agent/skill/pipeline does.
2. Why it exists — what problem it solves, what prompted it.
3. What it produces — the tangible output and who consumes it.

Use exact terminology that users will search for: agent names, tool names, product types,
intent keys. Include these naturally in prose (not a list). Complete sentences only.
-->

---

## Architecture

<!--
OPTIONAL — use for multi-component docs (agents, pipelines). Skip for howto/reference.
TARGET: ASCII diagram + brief caption. Max 30 lines.

Example:
```
Input
  |
  v
[Component A]  → does X
  |
  v
[Component B]  → does Y
  |
  v
Output
```
-->

---

## Components

<!--
TARGET: ≈200 words total. Table + one paragraph per component.

| Name | Role | Input | Output |
|------|------|-------|--------|
| ... | ... | ... | ... |

After the table, write one sentence per row explaining the role in context.
BM25 picks up table cell keywords; FAISS picks up the surrounding prose.
-->

---

## Configuration

<!--
TARGET: ≈100–150 words. JSON or YAML block + prose explanation.

```json
{
  "KEY_NAME": "value",
  "_note": "describe what this controls"
}
```

Explain each key in the prose below. BM25 picks up JSON keys; FAISS picks up prose.
Include environment variable names and where they're set (env var, st.secrets, etc.).
-->

---

## Quick Start

<!--
TARGET: ≈100 words. Bash commands + one sentence per command.
-->

```bash
# install
pip install -r requirements.txt

# run
python scripts/example/main.py --flag value
```

<!--
Describe what each command does in one sentence. Include expected output or side effects.
-->

---

## Triggers / Cadence

<!--
For automated/hooked components only. Skip for standalone tools.

| When | Event / Trigger | Output |
|------|----------------|--------|
| Daily 07:00 UTC | Cron | report.md committed to process/ |
| On request | User prompt | ... |
-->

---

## Citations

<!-- ISS-006: source citation system will populate this section automatically. Leave empty. -->

---

## Notes

<!--
Free-form. Edge cases, known limitations, future work, gotchas.
Keep under 100 words or split into a separate reference doc.
-->
