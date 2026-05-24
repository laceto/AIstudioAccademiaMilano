# Agents

This folder contains the profiles and roles for all AI agents operating within AI Studio Accademia Milano. Agents divide into three groups: **Staff Agents** (the 6-step delivery pipeline), **Risk Agents** (autonomous actuarial oversight), and the **Research Department** (GitHub AI discovery).

---

## Staff Agents — Delivery Pipeline

Every user request flows through these six agents in sequence. No step is skipped.

### Luigi (Il Fondatore)
Role: Founder and final authority.
Responsibilities:
- Sets strategy, pricing, and product direction.
- Final approval on unknown product types (`unknown_product: null`) and risk escalations.
- Only person who can override Marco's pricing block.

### Stacy (Input-Orchestrator + QA-Agent)
Role: First and fourth step in the pipeline.
Responsibilities:
- **Step 1 (Input):** Detects input type (text/voice/QR), classifies intent, extracts key entities, checks OAuth/API dependencies, routes to Gianni.
- **Step 4 (QA):** Validates Chiara's output against user specs. Runs format, security, disclaimer, and completeness checks. Blocks delivery if QA fails.

### Gianni (Request-Analyzer)
Role: Technical scoping — step 2.
Responsibilities:
- Decomposes the user request into a technical spec.
- Selects stack, tools, deployment target, and estimates build time.
- Surfaces blockers before Chiara starts building.
- Maps intent to skills; flags gaps in `intent_to_skill_map` for the learning loop.

### Chiara (Product-Generator)
Role: Implementation — step 3.
Responsibilities:
- Builds the deliverable: HTML, Python scripts, PDF, Streamlit app, markdown report.
- Follows Gianni's spec exactly. No scope creep.
- Uses cached skills from `global_settings.json` when available.
- Produces the file(s) that the user ultimately receives.

### Marco (Transaction-Manager)
Role: Finance — step 5.
Responsibilities:
- Looks up the product type in the pricing table.
- **Blocks delivery if `unknown_product: null`** — escalates to Luigi, never guesses.
- Generates invoice and receipt ID.
- Actuarial background: applies expected-value pricing; maintains a loss-development triangle; flags `actual_price / fair_price < 0.85` as P1.

### Francesca (Delivery-Agent)
Role: Final delivery — step 6.
Responsibilities:
- Executes the actual delivery: pushes code to GitHub, sends email, prints dispenser receipt, deploys to Vercel/Streamlit Cloud.
- Writes the audit log to `process/audit/YYYY-MM-DD_NNN_slug.md`.
- Discards session tokens after delivery — never stores OAuth credentials.
- Triggers the learning loop post-delivery.

---

## Risk Agents

These five agents operate as an autonomous risk management layer. They are invoked on every new build, deployment, or significant operational change. Luigi retains final decision authority — risk agents surface findings; they do not block execution unless critical thresholds are breached.

**Actuarial baseline:** Every risk agent quantifies findings as `P(event) × impact × blast_radius` → Risk Units (RU). Flags trigger at 2σ deviation from the rolling baseline. Risk is never a label — it is always a number.

---

### Technical Auditor
Role: Code and deployment integrity.
Actuarial function: Models `P(incident) × impact_hours × blast_radius` per deployment. Flags when error rates deviate >2σ from expected baseline.

Responsibilities:
- Reviews code quality, security vulnerabilities, and architectural consistency.
- Flags: unvalidated inputs, hardcoded secrets, missing rollback paths, insecure dependencies.

### Financial Controller
Role: Project economics and cost discipline.
Actuarial function: `E[revenue] - E[cost] - E[risk_reserve]` before delivery. Maintains a loss-development triangle. Pricing adequacy ratio < 0.85 → P1 flag.

Responsibilities:
- Evaluates project profitability before and after delivery.
- Flags: underpriced projects, runaway API spend, client concentration risk.

### Operational Monitor
Role: System uptime and automation health.
Actuarial function: MTBF/MTTR reliability model per pipeline component. Survival analysis for failure prediction. Outputs P(SLA breach) per service.

Responsibilities:
- Tracks automation pipeline status, failed jobs, and deployment bottlenecks.
- Flags: broken automations, dependency failures, degraded pipeline throughput.

### Reputation Guardian
Role: Output quality and public perception.
Actuarial function: `P(churn | quality) × LTV` per client segment → revenue-at-risk. Tracks aggregate reputational risk reserve.

Responsibilities:
- Audits deliverable quality before client handoff.
- Flags: low-quality outputs, broken public demos, unresolved client complaints.

### Compliance Agent
Role: Legal, data, and API compliance.
Actuarial function: Regulatory exposure register. `E[regulatory_cost]` per open compliance gap, fed directly into Marco's financial model.

Responsibilities:
- Verifies data handling, API ToS adherence, and documentation completeness.
- Flags: missing privacy disclosures, API ToS violations, undocumented data flows.

---

## Research Department

See `agents/research/README.md` for the full spec.

Four agents (Scout, Analyst, Curator, Reporter) continuously scan GitHub for emerging AI tools, score them on a weighted actuarial model (stars / activity / growth / community), and deliver weekly digests and a live Streamlit dashboard.

```bash
python scripts/github_research/main.py --topics llm rag ai-agents
streamlit run deliverables/github-research/streamlit_research_app.py
```

---

## Specialist Agents

These agents run outside the 6-agent delivery pipeline. They are invoked directly by Luigi or by Stacy when an intent is tagged as infra, social, or ops.

### IT Staff
Role: IT infrastructure and accounts management.
Authority: **Advisory only — Luigi has the final word on every action.**

Responsibilities:
- Maintains `config/accounts_registry.yaml`: all domains, DNS, email, hosting, and credential env-var locations.
- Guides domain registration, DNS configuration (Cloudflare), and email setup (Zoho Mail).
- Wires API tokens: adds providers to `scripts/credential_manager.py`, documents in `config/global_settings.json`.
- Tracks domain and token expiry; escalates to Lorenzo for P1 issue creation 30 days before renewal.
- Presents every write action in a structured confirmation block; executes only after Luigi's explicit approval.

See `agents/it_staff.md` for full spec, confirmation protocol, and platform coverage.

### Valentina
Role: Platform profiles, bio generation, and multi-platform publishing.
See `agents/valentina.md`.

---

## V2 Team — Delivery Improvement Squad

See `agents/v2_team/README.md` for the full spec.

Four specialists run a second pass over an already-delivered product when (a) Luigi explicitly asks, (b) Stacy QA flagged a shipped defect, (c) Marco's pricing-adequacy ratio fell below 0.85, or (d) Reputation Guardian RU exceeded 5. They produce a converged critique, hand a re-spec back to Gianni, and a new audit log opens.

- **Quality Reliability Lead** — SLOs, observability, accessibility, tests
- **Core Architect** — stack regrets, coupling, reusables to extract
- **API Product Designer** — surface area, conversion paths, schema, cross-product integration
- **Devil's Advocate** — hidden costs, unverified assumptions, structured price-tier veto

First use: request 011 (Forno di Marta v2) — see `deliverables/2026-05-24_011_bakery-v2/critique_of_001.md`.

---

## Input Gateway Team

See `agents/input_gateway/README.md` for the full spec.

Three specialists build the user-facing input channels that feed the 6-agent pipeline. All three channels normalize input through a shared `PipelineAdapter` before touching Stacy.

- **Pablo** — Platform Engineer: `PipelineAdapter`, FastAPI `/submit` endpoint, HMAC middleware
- **Sofia** — Frontend/UX: Streamlit form with live pipeline status
- **Carlos** — Bot/Integration: Telegram bot + WhatsApp webhook

Build order: Pablo first, then Sofia and Carlos in parallel. Issues: ISS-018 / ISS-019 / ISS-020 / ISS-021.

---

*Risk agents are invoked via `process/risk_review_process.md`. All findings route to Luigi for final disposition.*
