---
name: langgraph-dynamic-parallelism
description: Canonical patterns for LangGraph parallel fan-out using Send dispatch, fan-in aggregation, and Annotated reducer fields. Load when a workflow needs to run multiple nodes in parallel.
---

# LangGraph Dynamic Parallelism

## Send Dispatch (Fan-out)

Use `Send` to dispatch to multiple nodes in parallel from a routing function.

```python
from langgraph.types import Send

def dispatch_parallel(state: MyState) -> list[Send]:
    return [
        Send("node_a", state),
        Send("node_b", state),
        Send("node_c", state),
    ]

g.add_conditional_edges("intake_node", dispatch_parallel)
```

**Key rule:** The routing function must return `list[Send]` — not a string — to trigger parallel execution.

## Fan-in Aggregation

Parallel nodes converge at a single aggregator node. State fields that accumulate must use `operator.add`:

```python
import operator
from typing import Annotated

class MyState(TypedDict):
    # Each parallel node appends to this list — operator.add merges them
    parallel_reports: Annotated[List[dict], operator.add]
```

Each parallel node returns:
```python
def node_a(state, config) -> dict:
    return {
        "parallel_reports": [{"role": "node_a", "data": result}],
        "messages": [AIMessage(content="[NodeA] done")],
    }
```

Aggregator node reads the accumulated list:
```python
def aggregator(state, config) -> dict:
    reports = state.get("parallel_reports", [])
    a_data = next((r["data"] for r in reports if r["role"] == "node_a"), None)
    b_data = next((r["data"] for r in reports if r["role"] == "node_b"), None)
    return {"merged_result": {**a_data, **b_data}}
```

Wire convergence:
```python
g.add_edge("node_a", "aggregator")
g.add_edge("node_b", "aggregator")
g.add_edge("node_c", "aggregator")
```

## Mixed Routing (static + dynamic)

A routing function can return either a `str` (single node) or `list[Send]` (parallel):

```python
def route_after_intake(state: MyState) -> list[Send] | str:
    if state["workflow_type"] == "parallel":
        return [Send("node_a", state), Send("node_b", state)]
    return "single_node"
```

## This Repo's Pattern (from deliverable 016/029)

```python
# Fan-out for treaty/report workflows
def route_after_intake(state: BranchState) -> list[Send] | str:
    wf = state.get("workflow_type", "claim")
    if wf == "claim":
        return "medical_underwriter"          # single → sequential
    if wf == "treaty":
        return [
            Send("medical_underwriter", state),
            Send("actuarial_analyst",   state),
        ]
    return [
        Send("actuarial_analyst", state),
        Send("accountant",        state),
    ]
```

## Gotchas

- Parallel nodes receive a **copy** of state at dispatch time — they do not see each other's updates
- Only `Annotated[List[...], operator.add]` fields safely accumulate across parallel branches
- Do not use scalar fields to communicate between parallel nodes — they will overwrite each other
- The aggregator node runs once all parallel nodes have completed (LangGraph handles synchronisation)
