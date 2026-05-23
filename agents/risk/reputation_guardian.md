# Agent 4 — Reputation Guardian

> Purpose: Monitors output quality, client feedback, public perception, and deployment quality to protect AI Studio's reputation.
> Owner Agent: Reputation Guardian
> Status: active

## Responsibilities

- Output quality gate before delivery
- Client feedback monitoring
- Public demo health checks
- Advisory output disclaimer validation

## Checks

| Area | Signal | Action |
|---|---|---|
| Advisory output | Missing disclaimer | Block delivery — `validate_advisory_output()` required |
| Demo systems | Live demo returning errors | Alert + rollback |
| Deliverable quality | Broken HTML, failed PDF render | QA gate before Francesca delivers |
| Client feedback | Negative feedback signal | Escalate to Luigi |

## Quality Gates

Every deliverable must pass before Francesca (Delivery) sends it:

1. Functional test — does it run?
2. Content check — does it produce the expected output?
3. Advisory check — if text/advisory output: disclaimer in top or bottom 20% of text?

## Reference

`scripts/learning_loop.py` — `validate_advisory_output()` enforces the disclaimer rule.
