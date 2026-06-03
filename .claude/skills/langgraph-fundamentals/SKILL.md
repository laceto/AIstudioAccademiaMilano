---
name: langgraph-fundamentals
description: Canonical LangGraph patterns for this repo — StateGraph construction, TypedDict state, node functions, routing, and graph compilation. Load before writing any LangGraph StateGraph code.
---

# LangGraph Fundamentals

## Canonical State Pattern

```python
from __future__ import annotations
import operator
from typing import Annotated, List, Optional, TypedDict
from langchain_core.messages import BaseMessage
from langgraph.graph.message import add_messages

class MyState(TypedDict):
    # scalar fields — last-write-wins
    field: Optional[str]
    # list fields that accumulate across parallel nodes — use operator.add
    reports: Annotated[List[dict], operator.add]
    # message history — always use add_messages reducer
    messages: Annotated[List[BaseMessage], add_messages]
```

## Canonical Node Pattern

```python
from langchain_core.messages import AIMessage
from langchain_core.runnables import RunnableConfig
from .llm_factory import get_llm

def my_node(state: MyState, config: RunnableConfig) -> dict:
    provider = (config or {}).get("configurable", {}).get("provider", "anthropic")
    llm = get_llm(provider, "fast", max_tokens=1024, temperature=0)
    # ... invoke llm ...
    return {
        "field": result,
        "messages": [AIMessage(content="[MyNode] done")],
    }
```

**Rules for nodes:**
- Always return a dict — never mutate state directly
- Add an `AIMessage` with `[NodeName]` prefix to `messages` for traceability
- Accept `(state, config)` — LangGraph injects config automatically
- Use `llm_factory.get_llm(provider, tier)` — never hardcode a model name

## Canonical Graph Assembly

```python
from langgraph.graph import END, START, StateGraph

def build_graph():
    g = StateGraph(MyState)
    g.add_node("node_a", node_a)
    g.add_node("node_b", node_b)
    g.add_edge(START, "node_a")
    g.add_edge("node_a", "node_b")
    g.add_edge("node_b", END)
    return g.compile()
```

## Canonical Routing Function

```python
from typing import Literal

def route_after_node_a(state: MyState) -> Literal["node_b", "node_c"]:
    return "node_b" if state.get("some_condition") else "node_c"

g.add_conditional_edges("node_a", route_after_node_a)
```

## LLM Factory (always use this)

```python
# fast tier  → haiku-4.5 / gpt-4o-mini  (classification, extraction, routine)
# smart tier → sonnet-4.6 / gpt-4o       (reasoning, synthesis, complex output)
from .llm_factory import get_llm
llm = get_llm(provider, "fast", max_tokens=512, temperature=0)
```

## File Structure Convention

```
deliverables/YYYY-MM-DD_NNN_<slug>/
  __init__.py      exports build_graph() and run_*() helper
  state.py         TypedDict + any constants (e.g. pricing table)
  nodes.py         all node functions
  graph.py         StateGraph assembly + run_*() helper
  llm_factory.py   copy from any existing deliverable — never reinvent
  streamlit_app.py Streamlit UI (if needed)
  requirements.txt
```

## Running the graph

```python
initial_state = { ... }  # fully populated TypedDict
config = {"configurable": {"provider": "anthropic", "thread_id": "abc"}}

# batch
final = graph.invoke(initial_state, config=config)

# streaming (for Streamlit)
for event in graph.stream(initial_state, config=config, stream_mode="values"):
    msgs = event.get("messages", [])
    if msgs:
        print(msgs[-1].content)
```
