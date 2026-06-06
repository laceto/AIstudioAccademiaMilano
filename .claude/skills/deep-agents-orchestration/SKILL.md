---
name: deep-agents-orchestration
description: Supervisor patterns, agent handoffs, and orchestration conventions for multi-agent systems. Load when building a supervisor agent, managing agent-to-agent handoffs, or orchestrating a team of specialists.
---

# Deep Agents — Orchestration

## Supervisor Pattern

A supervisor node routes work to specialist agents and aggregates results:

```python
def supervisor(state: TeamState, config: RunnableConfig) -> dict:
    llm = get_llm(_provider(config), "fast", max_tokens=512, temperature=0)
    prompt = ChatPromptTemplate.from_messages([
        ("system", "You are a supervisor. Given the task, decide which specialist to call next. "
                   "Return JSON: {{'next': 'specialist_a|specialist_b|FINISH'}}"),
        ("human", "Task: {task}\nCompleted: {completed}"),
    ])
    result = (prompt | llm | JsonOutputParser()).invoke({
        "task": state["task"],
        "completed": state.get("completed_steps", []),
    })
    return {"next_agent": result["next"]}

def route_supervisor(state: TeamState) -> str:
    return "FINISH" if state["next_agent"] == "FINISH" else state["next_agent"]
```

## Handoff Convention

When one agent hands off to another, always document it in messages:

```python
return {
    "handoff_payload": {...},
    "messages": [AIMessage(content="[AgentA → AgentB] Handing off: <summary>")],
}
```

## Parallel Department Pattern (this repo — deliverable 016/029)

```python
def dispatch_departments(state: StudioState) -> list[Send]:
    return [
        Send("research_dept", state),
        Send("delivery_dept", state),
        Send("risk_panel",    state),
    ]

# Each department is a compiled subgraph
g.add_node("research_dept",  research_graph)
g.add_node("delivery_dept",  delivery_graph)
g.add_node("risk_panel",     risk_graph)
g.add_conditional_edges("supervisor", dispatch_departments)
```

## Agent Handoff Checklist

Before an agent hands off, it must:
- [ ] Complete its own state fields (no `None` values for required outputs)
- [ ] Append a summary `AIMessage` to `messages`
- [ ] Set `error: None` if successful
- [ ] Not modify fields owned by the receiving agent

## Escalation to Luigi (this repo)

Any agent can escalate to Luigi by setting:
```python
return {
    "escalate_to_luigi": True,
    "escalation_reason": "Specific reason string",
    "messages": [AIMessage(content="[AgentName] ESCALATING: <reason>")],
}
```

The `route_after_X` function then checks `state.get("escalate_to_luigi")` and routes to `luigi_escalate`.

## Convergence Guarantee

For parallel fan-out with `Send`, all dispatched nodes must converge at the same aggregator node. Ensure every parallel path has an `add_edge` pointing to the aggregator:

```python
for agent_name in ["medical_underwriter", "actuarial_analyst", "compliance_agent"]:
    g.add_edge(agent_name, "aggregator")
```
