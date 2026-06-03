---
name: langgraph-subagents
description: Canonical patterns for LangGraph subagents — nested graphs, agent-calls-agent, subgraph compilation, and state handoff between parent and child graphs. Load when an agent node needs to invoke another graph.
---

# LangGraph Subagents

## Subgraph as a Node

A compiled graph can be used directly as a node in a parent graph:

```python
# Build child graph
child_graph = build_child_graph()  # returns compiled graph

# Use as a node in the parent
parent = StateGraph(ParentState)
parent.add_node("child_agent", child_graph)
parent.add_edge("intake", "child_agent")
parent.add_edge("child_agent", "output")
compiled_parent = parent.compile()
```

State flows into the child and the child's output state is merged back into the parent.

## State Mapping (parent ↔ child)

When parent and child have different state schemas, use a mapping function:

```python
def invoke_child(state: ParentState, config) -> dict:
    child_input = {
        "task": state["task"],
        "context": state["context"],
    }
    child_result = child_graph.invoke(child_input, config=config)
    return {
        "child_output": child_result["output"],
        "messages": child_result.get("messages", []),
    }

parent.add_node("child_agent", invoke_child)
```

## Agent-as-Tool Pattern

For ReAct-style agents that call tools (including other agents):

```python
from langchain_core.tools import tool

@tool
def specialist_agent(task: str) -> str:
    """Invoke the specialist agent for deep analysis."""
    result = specialist_graph.invoke({"task": task})
    return result["output"]

# Main agent uses specialist as a tool
tools = [specialist_agent, web_search, calculator]
agent = create_react_agent(llm, tools)
```

## This Repo's Pattern (AI Studio → Department Subagents)

```python
# Parent: studio_graph routes to department subgraphs
def route_to_department(state: StudioState) -> list[Send]:
    return [
        Send("research_dept",  {"task": state["research_task"]}),
        Send("delivery_dept",  {"task": state["delivery_task"]}),
    ]
```

## State Isolation

- Each subgraph runs with its own state — no shared mutable state between parent and child
- Pass only what the child needs; receive only what the parent needs back
- Use `messages` for traceability — always append child messages to parent messages

## Checkpointing Subgraphs

Give each subgraph invocation a scoped thread ID to avoid checkpoint collisions:

```python
child_config = {
    "configurable": {
        "thread_id": f"{parent_thread_id}-child-{node_name}",
        "provider": provider,
    }
}
child_result = child_graph.invoke(child_input, config=child_config)
```
