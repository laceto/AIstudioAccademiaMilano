---
name: langgraph-persistence
description: Canonical patterns for LangGraph checkpointing and persistence — MemorySaver for dev, SQLite/Postgres for production, thread IDs, and state snapshots. Load when a workflow needs memory across invocations or HITL support.
---

# LangGraph Persistence

## Why Persistence Is Required

Without a checkpointer:
- Graph state is lost after each `.invoke()` / `.stream()` call
- HITL interrupts cannot be resumed
- Thread history is unavailable

## MemorySaver (dev / in-process)

```python
from langgraph.checkpoint.memory import MemorySaver

checkpointer = MemorySaver()
graph = g.compile(checkpointer=checkpointer)

# Thread ID scopes the memory — different IDs = independent conversations
config = {"configurable": {"thread_id": "user-123-session-1"}}

result = graph.invoke(initial_state, config=config)
```

## SQLite (lightweight production)

```python
from langgraph.checkpoint.sqlite import SqliteSaver

with SqliteSaver.from_conn_string("checkpoints.db") as checkpointer:
    graph = g.compile(checkpointer=checkpointer)
    result = graph.invoke(initial_state, config={"configurable": {"thread_id": "abc"}})
```

## Postgres (production at scale)

```python
from langgraph.checkpoint.postgres import PostgresSaver

DB_URI = "postgresql://user:pass@host/dbname"
with PostgresSaver.from_conn_string(DB_URI) as checkpointer:
    checkpointer.setup()  # run once to create tables
    graph = g.compile(checkpointer=checkpointer)
```

## Reading State History

```python
config = {"configurable": {"thread_id": "abc"}}

# Current state
snapshot = graph.get_state(config)
print(snapshot.values)    # full state dict
print(snapshot.next)      # next nodes to run (empty if finished)

# Full history
for state in graph.get_state_history(config):
    print(state.config)   # which checkpoint
    print(state.values)   # state at that point
```

## Thread ID Strategy (this repo)

```python
import uuid

# Per-case thread — preserves full history for a case
thread_id = f"case-{case_id}"

# Per-session thread — resets on new session
thread_id = f"session-{uuid.uuid4().hex}"

# Per-user thread — persistent across sessions
thread_id = f"user-{user_id}"
```

## Streamlit Pattern (session-scoped checkpointer)

```python
import streamlit as st
from langgraph.checkpoint.memory import MemorySaver

if "checkpointer" not in st.session_state:
    st.session_state.checkpointer = MemorySaver()

graph = g.compile(checkpointer=st.session_state.checkpointer)
```

## This Repo's Convention

- Development / demos: `MemorySaver` (no extra dependencies)
- Production deployments: `SqliteSaver` (zero-config, file-based)
- Always pass `thread_id` in config — never omit it when using a checkpointer
