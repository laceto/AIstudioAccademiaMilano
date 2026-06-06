---
name: deep-agents-core
description: Core principles and patterns for multi-agent systems in this repo — agent roles, state contracts, message tracing, error handling, and the 6-agent pipeline conventions. Load for any multi-agent implementation.
---

# Deep Agents — Core

## Agent Design Principles (this repo)

1. **Single responsibility** — each agent does one thing and outputs a typed result
2. **State-based communication** — agents communicate via shared TypedDict state, never direct calls
3. **Traceable messages** — every agent appends `AIMessage(content="[AgentName] ...")` to `messages`
4. **Idempotent nodes** — a node can be re-run safely (QA retries, HITL resume)
5. **Provider-agnostic** — always use `llm_factory.get_llm(provider, tier)`, never hardcode models
6. **Fast/smart tiers** — classification/extraction = fast; reasoning/synthesis = smart

## 6-Agent Pipeline Convention (canonical)

```
Step 1: Stacy (classify)   → Step 2: Gianni (scope) → Step 3: Chiara (implement)
Step 4: Stacy QA (validate) ← risk_aggregator ← [parallel risk agents]
Step 5: Marco (invoice)    → Step 6: Francesca (deliver)
```

Human-in-the-loop: `luigi_escalate` node intercepts unknown products or high-risk outputs.

## State Contract Rules

- **Required fields** — every state TypedDict must have: `messages`, `error`, `finished`
- **Optional fields** — use `Optional[T]` for fields that may not be set yet
- **Accumulated fields** — use `Annotated[List[dict], operator.add]` for parallel fan-in
- **No cross-agent mutation** — a node only writes fields it owns; never overwrites another agent's output

## Error Handling Pattern

```python
def my_node(state: MyState, config: RunnableConfig) -> dict:
    try:
        result = (prompt | llm | JsonOutputParser()).invoke(inputs)
        return {"my_field": result, "messages": [AIMessage(content="[MyNode] ok")]}
    except Exception as exc:
        return {
            "error": f"[MyNode] {exc}",
            "finished": True,
            "messages": [AIMessage(content=f"[MyNode] ERROR: {exc}")],
        }
```

## Routing After Error

```python
def route_after_node(state: MyState) -> str:
    if state.get("error"):
        return END
    return "next_node"
```

## Actuarial Risk Scoring (all risk agents)

Formula: `RU = P(event) × impact × blast_radius`

```python
def compute_risk_units(p_event: float, impact: float, blast_radius: float) -> float:
    return p_event * impact * blast_radius

# Flag if > 2σ from rolling baseline
BASELINE_RU = 2.0
SIGMA = 0.8
HIGH_RISK_THRESHOLD = BASELINE_RU + 2 * SIGMA  # = 3.6
```

## Output Validation (advisory outputs)

Any node producing advisory content must include a disclaimer:

```python
DISCLAIMER = (
    "This output is for informational purposes only and does not constitute "
    "regulated financial, legal, or actuarial advice."
)

return {"output": f"{DISCLAIMER}\n\n{content}"}
```

Validated by `scripts/learning_loop.py::validate_advisory_output()`.
