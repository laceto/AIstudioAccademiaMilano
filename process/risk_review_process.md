# Risk Review Process — 5-Agent Build Audit

Run this process on every new build, deployment, or major operational change before it goes live or is handed to a client.

**Owner**: Luigi (with findings from all 5 Risk Agents)
**Status**: active

---

## When to Run

Trigger this process when any of the following occur:

- A new software product, automation, or AI workflow is ready for deployment.
- A client deliverable is about to be handed over.
- Infrastructure configuration changes (new APIs, cloud services, credentials).
- A new agent or automated pipeline is activated.
- A public-facing demo or launch is scheduled.

Do not skip this process to save time. A failed deployment or breached client trust costs more than the review.

---

## Pre-Review Checklist

Before invoking the agents, gather the following:

- [ ] Build name and short description
- [ ] Deployment target (URL, repo, automation endpoint)
- [ ] Client or use context
- [ ] List of APIs, services, and third-party dependencies used
- [ ] Estimated project revenue and cost
- [ ] Any known issues or open items

---

## Agent 1 — Technical Auditor Review

**Checks to run:**

1. Code quality — are there obvious code smells, unhandled exceptions, or missing error boundaries?
2. Security — any hardcoded secrets, exposed credentials, unsanitized inputs, or insecure endpoints?
3. Deployment stability — does the deployment have a rollback plan? Is it idempotent?
4. Architecture consistency — does this build follow established patterns in the codebase?
5. Hallucination exposure — if AI-generated content is surfaced to users, is there a validation layer?
6. Dependency audit — are all third-party packages pinned and reviewed?

**Output:** Technical Audit Report (pass / conditional pass / fail + findings list)

**Escalation threshold:** Any security vulnerability, exposed secret, or missing rollback path = automatic hold until resolved.

---

## Agent 2 — Financial Controller Review

**Checks to run:**

1. Project profitability — does the quoted price cover time, infrastructure, and risk margin?
2. Infrastructure cost ceiling — what is the maximum monthly cost of this deployment at expected usage?
3. API spend projection — if LLM or third-party APIs are in the loop, what is the cost per transaction and at scale?
4. Client concentration check — does this client represent more than 40% of active revenue? If yes, flag.
5. Payment terms confirmed — is invoicing, deposit, or subscription setup confirmed before delivery?
6. Recurring revenue potential — does this build have a path to retained operations or subscription?

**Output:** Financial Viability Summary (approved / conditional / review required + line items)

**Escalation threshold:** Project cost exceeds quoted price by more than 20%, or no payment terms confirmed before delivery.

---

## Agent 3 — Operational Monitor Review

**Checks to run:**

1. Automation health — if this build includes scheduled jobs or automations, are they monitored?
2. Uptime expectations — what is the expected availability requirement, and is infrastructure sized for it?
3. Failure handling — what happens when this system fails? Does it degrade gracefully or hard-crash?
4. Pipeline status — are all integrations (webhooks, APIs, data feeds) confirmed live and tested?
5. Logging — is there sufficient logging to diagnose failures after deployment?
6. Alert configuration — are failure alerts routed to Luigi or a monitoring system?

**Output:** Operational Readiness Report (ready / requires fixes + gap list)

**Escalation threshold:** No logging in place, no failure handling, or critical integrations untested.

---

## Agent 4 — Reputation Guardian Review

**Checks to run:**

1. Output quality — review a sample of the system's outputs. Are they accurate, professional, and on-brand?
2. Demo reliability — if this will be shown publicly or to a client, run a full end-to-end demo and verify it does not break.
3. Client expectations alignment — does the deliverable match what was specified and promised?
4. Brand consistency — does any copy, interface, or communication reflect AI Studio standards?
5. Edge cases — what does the system do with unexpected or malformed inputs? Is the failure graceful?
6. Public perception risk — is there any content, output, or behavior that could embarrass AI Studio if screenshotted?

**Output:** Quality and Brand Clearance (cleared / conditional / hold + issues)

**Escalation threshold:** Demo fails during review, or output contains factual errors, offensive content, or misleading claims.

---

## Agent 5 — Compliance Agent Review

**Checks to run:**

1. Data handling — what personal or business data does this system collect, store, or process? Is there a privacy basis?
2. API terms compliance — review the terms of service for every external API used. Are the use cases permitted?
3. AI-generated content disclosure — if AI-generated content is delivered to an end user, is it disclosed where legally required?
4. Copyright exposure — does the system generate or reproduce content that could infringe third-party copyright?
5. Customer data governance — if client data is processed, is it isolated, not used for training, and deletable on request?
6. Documentation completeness — is there sufficient documentation for the client to understand what they are operating?

**Output:** Compliance Clearance (cleared / issues flagged + required actions)

**Escalation threshold:** Unresolved personal data handling without legal basis, or API ToS violation confirmed.

---

## Aggregated Risk Score

After all five agents complete their review, produce a composite risk assessment:

| Agent                  | Status                  | Critical Issues |
|------------------------|-------------------------|-----------------|
| Technical Auditor      | Pass / Conditional / Fail | count           |
| Financial Controller   | Approved / Review / Hold  | count           |
| Operational Monitor    | Ready / Fixes Required    | count           |
| Reputation Guardian    | Cleared / Conditional / Hold | count        |
| Compliance Agent       | Cleared / Issues Flagged  | count           |

**Overall Build Status:**
- GREEN — all five agents pass or conditionally pass with minor issues noted
- AMBER — one or more agents flagged issues requiring action before delivery; delivery may proceed with Luigi sign-off
- RED — any agent escalation threshold breached; delivery is on hold until resolved

---

## Luigi Decision Gate

Luigi reviews the aggregated report and makes one of three calls:

1. **Ship** — all clear, proceed to deployment and client delivery.
2. **Ship with conditions** — proceed with specific items logged as post-delivery follow-up.
3. **Hold** — do not deliver until named issues are resolved. Re-run the relevant agent review after fixes.

Luigi's decision is logged in the project record.

---

## Post-Deployment Follow-Up

Within 48 hours of going live:

- Operational Monitor confirms uptime and no failed jobs.
- Technical Auditor confirms no errors in production logs.
- Financial Controller confirms invoice sent or payment received.

Within 7 days:

- Reputation Guardian checks client feedback and any public reactions.
- Compliance Agent confirms no new regulatory flags.

---

## Record Keeping

Each risk review produces a named file:

`risk_review_[project-name]_[YYYY-MM-DD].md`

Stored in: `process/risk_reviews/`

This record is the audit trail for every build AI Studio ships.
