---
name: langgraph-human-in-the-loop
description: Canonical patterns for LangGraph human-in-the-loop — interrupt_before, interrupt_after, resuming a paused graph, and implementing approval gates in Streamlit. Load when a workflow needs a human decision point.
---

# LangGraph Human-in-the-Loop

## Compiling with Interrupts

```python
# interrupt_before: pause BEFORE the node runs — human can modify state first
graph = g.compile(interrupt_before=["approval_node"])

# interrupt_after: pause AFTER the node runs — human reviews output before continuing
graph = g.compile(interrupt_after=["approval_node"])
```

## Running to an Interrupt

```python
config = {"configurable": {"thread_id": "thread-abc"}}

# Graph runs until it hits the interrupt node, then pauses
events = list(graph.stream(initial_state, config=config, stream_mode="values"))
# Graph is now paused — state is saved in the checkpointer
```

## Inspecting Paused State

```python
snapshot = graph.get_state(config)
print(snapshot.next)        # which node will run next
print(snapshot.values)      # current state
```

## Resuming After Human Decision

```python
# Option 1: resume with state update (inject human decision)
graph.update_state(config, {"manager_decision": "approved"})
events = list(graph.stream(None, config=config, stream_mode="values"))

# Option 2: resume without changes (just continue)
events = list(graph.stream(None, config=config, stream_mode="values"))
```

## This Repo's Pattern (from deliverable 016/029)

```python
# Auto-approve mode for demos; HITL mode for production
def approval_node(state, config) -> dict:
    auto = (config or {}).get("configurable", {}).get("auto_approve", True)
    if auto:
        decision = "approved"
    else:
        decision = state.get("manager_decision", "pending")  # set externally via update_state

    return {
        "manager_decision": decision,
        "case_status": "approved" if decision == "approved" else "pending_info",
        "awaiting_approval": False,
        "finished": decision != "pending",
    }
```

Switch between modes via config:
```python
# Demo mode
config = {"configurable": {"provider": "anthropic", "auto_approve": True}}

# Production HITL mode
config = {"configurable": {"provider": "anthropic", "auto_approve": False}}
```

## Streamlit HITL Integration

```python
# In streamlit_app.py — poll for pending state
snapshot = graph.get_state(config)
if "approval_node" in snapshot.next:
    st.warning("Awaiting approval from Branch Manager")
    decision = st.radio("Decision", ["approved", "rejected"])
    if st.button("Submit decision"):
        graph.update_state(config, {"manager_decision": decision})
        # resume
        for event in graph.stream(None, config=config, stream_mode="values"):
            st.write(event.get("messages", [{}])[-1].get("content", ""))
```

## Requirements

HITL requires a **checkpointer** — without it, graph state is lost between invocations:

```python
from langgraph.checkpoint.memory import MemorySaver

checkpointer = MemorySaver()
graph = g.compile(checkpointer=checkpointer, interrupt_before=["approval_node"])
```

For production persistence use `langgraph-checkpoint-postgres` or `langgraph-checkpoint-sqlite`.
