---
name: deep-agents-memory
description: Cross-session memory patterns for agents — project_state.md, MemorySaver vs persistent checkpointers, per-user memory stores, and the learning loop memory conventions for this repo.
---

# Deep Agents — Memory

## Memory Types

| Type | Scope | Implementation |
|------|-------|---------------|
| In-graph state | Single run | TypedDict state fields |
| Thread memory | Across runs, same thread | LangGraph checkpointer (MemorySaver/SQLite) |
| Project memory | Across sessions | `~/.claude/projects/.../memory/project_state.md` |
| Long-term agent memory | Across all projects | `~/.claude/CLAUDE.md` |

## Thread Memory (LangGraph Checkpointer)

See `langgraph-persistence` skill. Key convention for this repo:

```python
# Thread ID per case/user — enables resuming interrupted workflows
config = {"configurable": {"thread_id": f"case-{case_id}", "provider": "anthropic"}}
```

## Project State Memory (this repo)

The learning loop writes a project memory file after each session:

```
~/.claude/projects/-home-user-AIstudioAccademiaMilano/memory/project_state.md
```

This file captures: last delivered request ID, open issues, skills promoted, pattern counters.

Reading project memory in an agent:
```python
from pathlib import Path
import os

state_path = Path(os.environ.get("HOME", "~")) / ".claude" / "projects" / \
    "-home-user-AIstudioAccademiaMilano" / "memory" / "project_state.md"

if state_path.exists():
    project_memory = state_path.read_text()
```

## Per-Agent Memory Store

For agents that need structured memory across sessions:

```python
from langgraph.store.memory import InMemoryStore

store = InMemoryStore()

# Write
store.put(("user", user_id, "preferences"), "pref_key", {"value": "data"})

# Read
items = store.search(("user", user_id, "preferences"))
```

For persistent storage: use `langgraph-store-postgres` or write to a JSON file.

## This Repo's Memory Convention

1. **Session end** → `learning_loop.py` writes `project_state.md` and promotes skills
2. **Session start** → SessionStart hook syncs agents and skills to `~/.claude/`
3. **Audit logs** → `process/audit/YYYY-MM-DD_NNN_slug.md` are the canonical memory of what was built
4. **RAG index** → `scripts/rag/embed_repo.py` indexes the full repo as searchable memory

## Injecting Memory into Agent Context

The `UserPromptSubmit` hook injects top-5 relevant repo chunks before every response:

```bash
# This runs automatically — do not call manually
python -m scripts.rag.inject_context
```

To query project memory manually:
```bash
python -m scripts.retrieve "how does Marco price unknown products?"
```
