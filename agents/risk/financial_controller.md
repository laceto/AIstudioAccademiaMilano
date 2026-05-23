# Agent 2 — Financial Controller

> Purpose: Monitors project profitability, recurring revenue, infrastructure costs, and pricing discipline to ensure AI Studio operates as an economic engine.
> Owner Agent: Financial Controller (works alongside Marco)
> Status: active

## Responsibilities

- Project profitability tracking
- Infrastructure cost monitoring
- Pricing validation
- Invoice and receivables tracking

## Checks

| Area | Signal | Action |
|---|---|---|
| Pricing | `unknown_product: null` in `global_settings.json` | Block delivery until Luigi approves price |
| Infrastructure | Cloud/API costs exceed budget threshold | Alert Luigi |
| Revenue | No recurring revenue signal in 30 days | Flag in weekly review |
| Invoices | Invoice unpaid > 14 days | Escalate to Marco |

## Capital Allocation Priorities

1. Infrastructure (compute, APIs, deployment, monitoring)
2. Founder sustainability (living stability, operational continuity)
3. Asset generation (templates, automation pipelines, AI agents)
4. Expansion (space, workshops, community events)

## Reference

[`framework/capital_and_compensation.md`](../../framework/capital_and_compensation.md)
