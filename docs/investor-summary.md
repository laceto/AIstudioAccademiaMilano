# AI Studio Accademia Milano — Investor Summary

As of 2026-11-12. Founder: Luigi Aceto.

A one-founder studio that turns a plain request into a priced, built and delivered product through a pipeline of AI agents. Built in under six months, with 541 commits and 1,494 automated tests, and still pre-revenue.

All figures below were counted from the repository on the date above, not copied from older docs. A published copy of this summary exists as a Claude Doc; this file is the version that lives with the code.

## Why this exists

People and small businesses want a finished output, not a project: a landing page, an invoice PDF, a chatbot, a calendar sync. The studio sells exactly that at a fixed price (€0.50 to €45.90) and builds it with AI agents instead of staff.

- **One human, many agents.** The founder sets strategy and prices and approves anything the system has not seen before. Everything else is agent work.
- **Fixed price list, fail closed.** Every product has a price key. A request that matches no key has price `null` and is blocked until the founder approves a price.
- **Actuarial risk layer.** Five risk agents score every step as probability × impact × blast radius (Risk Units) and flag at 2σ.
- **Four ways in:** Telegram bot (live), a physical QR-code dispenser with Stripe payment, GitHub Actions or issues, and a CLI.

## Traction in numbers

| Measure | Value |
|---------|-------|
| First commit / latest commit | 2026-05-23 / 2026-11-12 |
| Commits / merged pull requests | 541 / 108 |
| Python files / lines | 404 / about 59,900 |
| Automated tests | 1,494 (66 test files) |
| CI/CD workflows (GitHub Actions) | 9 |
| Delivered requests logged | 54 (57 audit logs, 58 deliverable folders) |
| Audit outcomes recorded | 44 success, 5 partial |
| Agents defined | 24, plus the founder |
| Skills registered in studio settings | 72 |

## How a request becomes a product

Every request passes six steps in order; none is skipped.

1. **Stacy** classifies the intent, checks the price key and blocks unknown products.
2. **Gianni** scopes the work: stack, requirements, risk surface.
3. **Chiara** builds the deliverable (code, PDF, template, content).
4. **Stacy QA** validates format, security and the mandatory disclaimer on advisory output.
5. **Marco** computes cost, margin and the invoice; he blocks delivery on a `null` price and escalates to the founder.
6. **Francesca** delivers (push, email, deploy), writes the audit log and triggers the learning loop.

**Pipeline v2** (built alongside v1, selected with `PIPELINE_VERSION`, v1 stays the default) adds an injection scan by Lorenzo, a Devil's Advocate, Financial Controller and IT Staff review before the build, six parallel reviewers after it, a Core Architect on trigger, a drafted announcement by Valentina, and an aggregator with a critical-finding threshold.

**Human gate.** For new or unpriced requests the founder gets a Telegram card with Approve, Free, Set price and Reject buttons. Only his numeric Telegram ID is accepted, once per job.

## The agent roster

24 agents are defined in `.claude/agents/`, plus the founder as final authority.

| Group | Agents | Count |
|-------|--------|-------|
| Delivery pipeline | Stacy (intake and QA), Gianni, Chiara, Marco, Francesca | 5 |
| Risk oversight | Technical Auditor, Financial Controller, Operational Monitor, Reputation Guardian, Compliance Agent | 5 |
| Input gateway builders | Pablo (API), Sofia (Streamlit form), Carlos (Telegram and WhatsApp) | 3 |
| GitHub research department | Scout, Analyst, Curator, Reporter (two sets exist: `research-*` and the originals) | 4 |
| V2 review squad | API Product Designer, Core Architect, Devil's Advocate, Quality Reliability Lead | 4 |
| Specialists | Lorenzo (prompt-injection scan), IT Staff (advisory only), Valentina (brand voice and publishing) | 3 |

Standing rules: every agent logs a mistake the moment it finds one (`process/mistake_log.md`), and IT Staff only advises; the founder decides every infrastructure action.

## Products and pricing

The catalogue has 19 priced products; anything else is blocked for the founder to price.

| Price band | Products |
|------------|----------|
| €0.50 to €3.90 | Email delivery, PDF document, invoice PDF |
| €4.90 to €9.90 | Strategic report, static landing page, weather dashboard, mind dashboard (journal) |
| €14.90 | Calendar integration, micro-syllabus and flashcards, family archivist, Mediterranean meal planner, Niccolò chronicles, bank statement analyst |
| €19.90 to €29.90 | Chatbot app, Streamlit agent deploy, algo trading (€24.90), premium landing page, RAG knowledge base |
| €45.90 | Commercial landing page |

**What has been delivered.** Of the 54 requests in the delivery table, 23 carry a price, adding up to €309.20 at list price. 28 are internal tooling at €0.00, and 3 wait for the founder to set a price (proposals of €4.90, €14.90 and €29.90).

Examples: a bakery website, invoice PDFs with Gmail delivery, a Streamlit chatbot, a RAG system over a codebase, an Alpaca paper-trading bot with dashboard, a Milan weather dashboard, a bank statement analyst, a calendar sentinel with Telegram alerts, and a psychology-vertical SOAP note generator (pilot).

## Internal processes and procedures

The studio runs on written procedures that agents and the founder follow. Each row names where it lives in the repo.

### Delivery procedure and definition of done

| Step | Rule | Where |
|------|------|-------|
| Classify | Map the request to one of 17 intents (skills and delivery options per intent) or to a price key; no match means `unknown_product: null`, which blocks delivery and escalates to the founder | `CLAUDE.md`, `process/intent_registry.yaml`, `process/User_Request_to_Delivery.md` |
| Framework gate | Any LangGraph, LangChain or multi-agent request must load the matching framework skills before code is written; a hook injects the reminder on every prompt | `scripts/agentic_skill_router.py` |
| Break down, then build | Non-trivial code is decomposed first and implemented leaf by leaf; tests are written first and must fail before the implementation | `CLAUDE.md` (Testing), `breakdown` skill |
| Done means three artifacts | An audit log, a deliverable folder and a row in the Delivered Requests table; new pricing is also written to `config/global_settings.json` in the same commit | `CLAUDE.md` (Delivery checklist, Delivery ID policy) |
| IDs | The audit filename is the canonical ID; IDs are globally unique and increase by one; internal tooling without an audit uses `—` | `process/audit/` |
| Pre-push check | Last audit number is correct and the ID appears exactly once in the table | `CLAUDE.md` |
| Ship | One fresh `claude/<slug>` branch per feature, never a push to `main`; commit, push, open the PR and merge it without asking again, except for destructive operations, commits touching `.env` or credentials, or work the founder paused | `CLAUDE.md` (Active Branch) |

### Risk review (before any build goes live)

Five risk agents review every new build, deployment, infrastructure change or client handover. The owner is the founder.

| Agent | What it checks | Automatic hold when |
|-------|----------------|---------------------|
| Technical Auditor | Code quality, security, rollback, architecture fit, hallucination exposure, pinned dependencies | A vulnerability, an exposed secret or no rollback path |
| Financial Controller | Margin, infrastructure ceiling, API spend per transaction, client concentration above 40%, payment terms | Cost exceeds the quote by more than 20%, or no payment terms |
| Operational Monitor | Monitoring, uptime, failure handling, integrations tested, logging, alerts | No logging, no failure handling, or critical integrations untested |
| Reputation Guardian | Output quality, a full end-to-end demo, fit with what was promised, brand, edge cases | The demo fails, or outputs contain errors or misleading claims |
| Compliance Agent | Personal data basis, API terms of service, AI-content disclosure, copyright, deletable client data, documentation | Personal data without a legal basis, or a confirmed terms violation |

The result is GREEN (all pass), AMBER (issues; ships only with founder sign-off) or RED (on hold). The founder then decides: ship, ship with conditions, or hold. Follow-ups: within 48 hours uptime, logs and invoice are confirmed; within 7 days client feedback and new regulatory flags are checked. Every review is meant to be filed as `risk_review_<project>_<date>.md`.

### Learning loop and mistake log

- **Trigger:** every session end and every confirmed delivery run `scripts/learning_loop.py` through hooks.
- **What it learns:** new skills, agent capabilities, recurring patterns promoted to hooks (thresholds: security 1 occurrence, external API write 2, skill preload 3), new MCP endpoints, and written lessons (cue, lesson, evidence, confidence) from each audit log.
- **Change control:** each settings change gets a risk score. Below 3 it is committed automatically; 3 to 4 needs the founder's approval; 5 or more is blocked until he signs off. The score that decides is the one in the delivery's audit log.
- **Output:** `config/global_settings.json` is updated and `process/lessons_learned.md` is regenerated; Gianni and Chiara read it before starting.
- **Mistake log:** every agent must record a mistake the moment it is found, one entry per incident (`ML-NNN`), reviewed weekly by the founder. It covers systems and processes, not people.

### Hooks that run on every session

| Event | What runs |
|-------|-----------|
| SessionStart | Activates the pre-commit secret scanner; copies the repo's agents and skills into the user's Claude config |
| UserPromptSubmit | Retrieves the top 5 relevant chunks from the repo index and injects them; injects the agentic-framework skill reminder |
| PreToolUse (Gmail) | Checks the OAuth token before any Gmail call |
| PostToolUse (GitHub push) | Runs the learning loop for a completed delivery |
| Stop | Runs the learning loop, collects the day's delta from the audit logs, and writes a crash-recovery checkpoint to `project_state.md` |

### Scheduled and automatic operations

| What | When | Where |
|------|------|-------|
| Tests and CI | Every push and pull request | `ci.yml` |
| Gateway smoke test | Every change under `gateway/**`; deployed variant by hand | `gateway-smoke.yml` |
| Learning loop commit | Every push | `studio-ops.yml` |
| Wiki checks (syntax and execution of code examples, internal links) | Every push and pull request, plus Sundays 10:00 UTC | `wiki-maintenance.yml` |
| Repo index rebuild for retrieval | Daily 06:00 UTC and on push | `rag-maintenance.yml`, `rag-bootstrap.yml` |
| GitHub AI research report and issue | Wednesdays 19:17 UTC | `research_schedule.yml` |
| Weekly content drop (Valentina) | Mondays 09:00 UTC | `digital_presence.yml` |
| Pipeline run | By hand or when a GitHub issue is opened | `pipeline.yml` |
| Stuck-job sweep | Every 10 minutes (Cloud Scheduler); jobs stuck in `running` become `failed` and are never re-run automatically | `gateway/recovery.py` |
| Gmail tidy | Hourly (Cloud Scheduler), dry run until switched live | `mailagent/` |
| Research digest for Gianni | Weekly; the Scheduler job is documented but was not yet created when delivery 040 was recorded | `process/runbook_research_digest.md` |

### Security and data-handling procedures

- **Secrets:** API keys live in environment variables, Streamlit secrets or Secret Manager, never in code. A pre-commit scanner blocks staged `.env` files and known credential patterns; bypass only for a confirmed false positive.
- **Credentials:** OAuth tokens are scoped to the session and never saved or logged (`scripts/credential_manager.py`); Apple Calendar uses only app-specific passwords.
- **Untrusted input:** Lorenzo and `scripts/injection_detector.py` scan web pages, API responses and pasted content for prompt injection before any agent acts on them.
- **Entry points:** gateway `/submit` and `/status` need an `X-API-Key` and answer 503 when no key is configured; webhooks are signed (HMAC-SHA1 on Twilio); rate limiting runs before the key check.
- **Advisory output:** a validator enforces the mandatory disclaimer.
- **Retention and privacy:** jobs expire after 90 days (30 for refusals) through Firestore TTL; `/privacy` gives the notice; the founder answers access and erasure requests within one month using a runbook, and `/cancella` deletes exactly the named data and records the erasure without personal details.
- **Refusals:** clearly illegal requests are refused by a phrase filter and then the model; the customer can ask for review (`RIESAMINA`), which alerts the founder without creating a job.
- **Authority:** only the founder's numeric Telegram ID can approve, price, reject or send results, once per job. IT Staff is advisory only.

### Operational runbooks

| Runbook | Covers |
|---------|--------|
| `process/runbook_cloudrun.md` | Deploy the Telegram channels to Cloud Run in six steps (project, secrets, build, deploy, webhooks, test), known trade-offs, rollback to the laptop |
| `process/runbook_local_telegram_stack.md` | Run the whole Telegram stack on a laptop without a public URL; clear stale webhooks first; troubleshooting |
| `process/runbook_mailagent_cloudrun.md` | Gmail tidy: dry run first, go live with `--live`, undo by moving mail back, failure table |
| `process/runbook_privacy_requests.md` | Identify the customer, find the data in Firestore, give access or erase it, log the erasure |
| `process/runbook_research_digest.md` | Weekly GitHub digest and the Scheduler command |
| `scripts/check_telegram.py` | Doctor for Telegram bots: detects webhook and polling conflicts and duplicate tokens |
| `scripts/deploy_cloudrun.sh` | One-command deploy with a `--dry-run` preview |

### Planning, reporting and white-label procedures

- **Requirements:** Gianni runs a requirements checker before scoping; the intent registry lists skills and delivery options per intent.
- **Reporting:** `scripts/log_analytics.py` computes delivery and revenue metrics from the audit logs; a delta collector summarizes each day; `sync_issues.py` keeps the issue table in step.
- **Planning documents:** a 90-day onboarding plan, a 90-day community roadmap, a platform profile setup checklist (Valentina) and role assignments for the launch.
- **White label:** a suit schema and `scripts/suit_manager.py` (`list`, `show`, `create`) replicate the studio for other verticals; S001 is the original studio and S002 a reinsurance branch.
- **Simulations:** written walk-throughs of the text-input and PDF-email flows used to rehearse the pipeline.

## Platform built internally

| Capability | What it does | Status |
|------------|--------------|--------|
| Input gateway | FastAPI `/submit` and `/status` behind an `X-API-Key` that fails closed; Telegram and WhatsApp bots; Streamlit form | Telegram live on Cloud Run (europe-west8) since 2026-10-09; WhatsApp and form not live |
| Approval and pipeline worker | Founder approves from Telegram; LangGraph pipeline runs on a private Cloud Run worker via Cloud Tasks; jobs in Firestore | Deployed |
| Privacy and safety | 90-day retention with Firestore TTL, `/privacy` notice, `/cancella` erasure on request, automatic refusal of clearly illegal requests, recovery of stuck jobs | Deployed |
| Research department | Scout, Analyst, Curator, Reporter scan GitHub and trending AI repos; weekly digest feeds Gianni | Running on a schedule |
| Learning loop | Each delivery's audit log can record lessons (cue, lesson, evidence, confidence) that Gianni and Chiara read before starting | Running |
| Bank statement analyst | Credem, ING and Fineco PDFs to classified movements and Excel per bank; balances reconcile; verified on real statements (1,466 movements, giroconti paired) | Working locally |
| Mail and calendar agents | Gmail tidy and to-do agent, calendar sentinel with Telegram alerts | Built, not yet proven on real accounts |
| Drive semantic router | Sorts a Drive inbox by meaning (MiniLM and ChromaDB), dry run by default | Built, not deployed |
| CI smoke tests | Simulated request through the gateway and the pipeline worker on every change to `gateway/**` | Running in GitHub Actions |

## Tech stack

| Layer | Technology |
|-------|------------|
| Language and tests | Python, pytest (1,494 tests), GitHub Actions |
| Agent frameworks | LangGraph, LangChain, deepagents, Claude Code subagents and skills |
| Models | OpenAI (gpt-4o, embeddings, Batch API via kitai), Anthropic Claude, local Ollama for summaries |
| Retrieval | FAISS plus BM25 hybrid search, ChromaDB, sentence-transformers (MiniLM) |
| Apps and APIs | FastAPI, Streamlit, python-telegram-bot, Twilio (WhatsApp), Stripe |
| Documents | fpdf2, pdfplumber, openpyxl |
| Cloud | Google Cloud Run, Cloud Tasks, Cloud Scheduler, Cloud Build, Artifact Registry, Firestore, Secret Manager (project `aistudio-milano`, europe-west8); Azure App Service F1 and Key Vault for the Drive router |
| Integrations | Gmail, Google Calendar, Google Drive, Microsoft Graph, Apple CalDAV, GitHub |
| Security | Secrets only in env or Secret Manager, pre-commit secret scan, HMAC on webhooks, fail-closed API key |

## What is proven, and what is not yet

The studio is pre-revenue. The studio wiki records €0 collected, blocked on the Italian VAT number (ISS-011). The €309.20 above is list price of delivered items, not cash received.

- **Proven:** the six-step pipeline, the Telegram request flow with founder approval, privacy and erasure handling, and the bank analyst on real statements.
- **Unproven against real services:** the mail agents, calendar sentinel, Drive router and Claude Code build engine were tested offline only; their own delivery notes say so.
- **Not deployed:** the API-key-protected gateway (ISS-031), the separate admin bot (ISS-029), WhatsApp and the Streamlit form (ISS-021).
- **Switched off on purpose:** Chiara's Claude Code build engine, until the founder decides where generated code may run (ISS-032).
- **Process written down more than exercised:** the mistake log has one entry, and the `process/risk_reviews/` folder that the risk-review procedure names does not exist yet, so no risk-review record has been filed there.
- **Unit economics:** Marco computes cost and margin per request, but this summary does not report them; they were not checked here.

## Next steps that gate revenue

| Issue | Priority | What has to happen |
|-------|----------|--------------------|
| ISS-011 | P1 | Get Stripe, Twilio, Telegram credentials and the VAT number so money can be collected |
| ISS-031 | P1 | Deploy the protected gateway and run the deployed smoke test |
| ISS-025 | P3 | Pick a merchant of record for EU VAT; the evaluation recommends Payhip over Lemon Squeezy |
| ISS-021 | P2 | Bring WhatsApp and the Streamlit form live beside Telegram |
| ISS-032 | P2 | Decide where Claude Code builds may run, then switch the engine on |
| Pricing | n/a | Set prices for the three pending products |
