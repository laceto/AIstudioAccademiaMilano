# V2 Team — Delivery Improvement Squad

> Purpose: Raise the value and reliability of any delivered product by running it through a second pass with four specialists. Used for v2 rebuilds, post-mortems, and "should we have shipped this?" reviews.
> Status: active (introduced request 011 — Forno di Marta v2)

## When the V2 Team is invoked

The team runs **after** the canonical 6-agent pipeline, not inside it. Trigger conditions:

1. **Explicit user request** — "improve delivery N", "v2 this", "make this better"
2. **Stacy QA flagged a known defect that shipped anyway** (e.g. placeholder image in request 001)
3. **Marco's pricing adequacy ratio < 0.85** (we left value on the table)
4. **Reputation Guardian RU > 5 on a delivered product** (post-delivery risk surfaced)

## Composition

| Agent | Role | Primary lens |
|---|---|---|
| Quality Reliability Lead | Quality, SLOs, observability, accessibility, testability | Will it work tomorrow at 2 AM? |
| Core Architect | Stack, coupling, build system, evolvability | Can we change this in six months without rewriting? |
| API Product Designer | Surface area, conversion path, schema, cross-product integration | Who calls this thing, why, and what do they get back? |
| Devil's Advocate | Hidden costs, unverified assumptions, ops burden on the user | Is the customer actually going to use this? Who pays for it? |

The four agents work in **parallel**, then converge into a single shared recommendation. If they disagree, the Devil's Advocate has structured veto power on the recommended price tier (they cannot block features, only flag that the price is too high for the delivered value).

## Workflow

```
Original delivery (e.g. 001 bakery)
    |
    v
Trigger detected (user request / QA flag / Marco / Reputation Guardian)
    |
    v
[4 V2 agents in parallel]
    Quality Reliability Lead    -> defects, missing SLOs, a11y/perf gaps
    Core Architect              -> stack regrets, refactor surface
    API Product Designer        -> missing conversion paths, integration gaps
    Devil's Advocate            -> hidden costs, ops burden, ROI challenge
    |
    v
Converged critique document    (deliverables/<date>_<id>_<slug>/critique_of_NNN.md)
    |
    v
Re-spec handed to Gianni       (treated as a new request — full 6-agent pipeline)
    |
    v
v2 delivery + new audit log    (process/audit/<date>_<new_id>_<slug>.md)
```

## Handoffs

- **Receives from**: Stacy QA, Marco (pricing adequacy flag), Reputation Guardian, Luigi (explicit ask)
- **Sends to**: Gianni (as a re-spec) and Marco (for new SKU pricing if applicable)
- **Logs to**: the v2 delivery's audit log under `agents_invoked` with role tag `v2_team`

## Reference

- [`quality_reliability_lead.md`](./quality_reliability_lead.md)
- [`core_architect.md`](./core_architect.md)
- [`api_product_designer.md`](./api_product_designer.md)
- [`devils_advocate.md`](./devils_advocate.md)
- First use: [`deliverables/2026-05-24_011_bakery-v2/critique_of_001.md`](../../deliverables/2026-05-24_011_bakery-v2/critique_of_001.md)
