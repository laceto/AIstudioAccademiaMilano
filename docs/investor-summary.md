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
