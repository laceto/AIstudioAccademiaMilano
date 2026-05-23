# Brainstorm: Human-in-the-Loop (HITL) System
Date: 2026-05-23  
Owner: Stacy (orchestration) + Gianni (technical)  
Status: Brainstormed — pending decision

---

## Problem Statement
How might we give a solo founder meaningful, low-friction control over autonomous AI agents without defeating the purpose of automation?

## Goal Statement
A HITL system where Luigi can tune — globally or per-agent — how often and at which decision points human approval is required, so he stays in control without becoming a bottleneck.

## Constraint Statement
One human operator (Luigi). LangGraph as the execution runtime. Workflows must still be usable when Luigi is offline. No enterprise budget for custom tooling from scratch.

---

## Key Angles

### Technical Primitives
- LangGraph native `interrupt()` / `interrupt_before` / `interrupt_after` at node level
- State persistence (checkpointer) required for pause/resume
- Global toggle via `config["configurable"]["hitl_enabled"]`
- Granular control = HITL policy layer: `(agent_id, node_name, action_type)` → `(block | notify | auto)`

### Business Logic
- HITL is a trust-building scaffold — not a permanent tax
- Agents should "earn" autonomy through demonstrated reliability
- Cost: latency + attention. Value: error prevention + reputational coverage.

---

## Alternatives Considered

| Alternative | Rationale |
|---|---|
| Global toggle only | Shippable today; forces discovery of what matters |
| Risk-tier routing (Low/Medium/High) | Mirrors circuit breakers; reserves attention for high-stakes only |
| Approval budget per run (N slots) | Forces prioritization; prevents interrupt storms |
| Slack-native approval UI | Zero new UI surface; Luigi already lives there |
| Time-decay autonomy | HITL self-eliminates where agents prove reliable |
| Shadow mode (async review) | Zero latency cost; detection only, not prevention |

---

## Key Risks

| Risk | Level | Mitigation |
|---|---|---|
| Interrupt storms — Luigi drowns | High | Cap N interrupts per workflow run |
| Orphaned workflows on no-response | High | Timeout + fallback policy (auto-approve or auto-abort) |
| Friction kills use — HITL disabled and never re-enabled | High | Slack one-click UX; default to rare interrupts |
| HITL prevents scale | High | Build autonomy-earning from day one |
| Rubber-stamp approvals | Medium | Log response time; surface in audit |

---

## Hidden Assumptions
- Luigi responds promptly (if not: need timeout policies)
- Agent actions are discrete decision points (if not: rethink what interrupt means)
- Single approver forever (if not: need role-based routing)
- HITL actually reduces errors (if not: fix prompts instead)
- Approval UX is low-friction (if not: rubber-stamping risk)

---

## Recommended Implementation Sequence

1. **Define HITL policy schema** → `hitl_policy.yaml` in repo
2. **Global on/off + persistent checkpointer** → all graphs interruptable
3. **First interrupt node on Stacy** → highest-risk external action → Slack approval
4. **Timeout + fallback behavior** → no workflow hangs indefinitely
5. **2-week instrumentation review** → tune policy, move reliable nodes to `auto`

---

## Key Open Question
> What is the highest-risk action any current agent takes — the one where an autonomous mistake would be most costly or hardest to reverse?  
> That node is where HITL lands first.
