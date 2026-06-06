---
name: agentic-router
description: Routes agentic/LangGraph/LangChain tasks to the correct framework skills. Invoke this FIRST whenever the task involves StateGraph, multi-agent systems, subagents, persistence, HITL, or RAG chains. Returns a routing decision and which skills to load next.
---

# Agentic Router

Analyse the task and return a routing decision. Then instruct the user/Claude to load the recommended skills before writing any code.

## Routing Table

| Task involves | Load these skills |
|---------------|------------------|
| StateGraph, nodes, edges, routing functions | `langgraph-fundamentals` |
| `Send` dispatch, parallel fan-out, fan-in | `langgraph-dynamic-parallelism` |
| Nested agents, subgraphs, agent-calls-agent | `langgraph-subagents` |
| Checkpointing, thread IDs, memory across runs | `langgraph-persistence` |
| `interrupt_before/after`, human approval gate | `langgraph-human-in-the-loop` |
| Supervisor pattern, multi-agent orchestration | `deep-agents-core` + `deep-agents-orchestration` |
| Cross-session memory, long-term agent state | `deep-agents-memory` |
| LCEL chains, prompts, output parsers | `langchain-fundamentals` |
| Vectorstores, retrieval, RAG pipelines | `langchain-rag` |
| Callbacks, tracing, middleware | `langchain-middleware` |

## Output format

```
AGENTIC ROUTER DECISION

Task type: <what was detected>
Skills to load: <comma-separated list>
Load order: <sequential if dependencies exist, parallel otherwise>

Proceed: invoke each skill above before writing any implementation code.
```

## Rules

- Never skip routing — even if confident about the implementation
- If multiple skill areas apply, load all of them
- Skills encode canonical conventions for this repo — they override default LangGraph/LangChain patterns
- After loading skills, confirm the canonical pattern before writing code
