# AI Studio Accademia Milano — Investor Summary

As of 2026-11-12. Founder: Luigi Aceto.

A one-founder studio that takes a request, classifies it, prices it from a price table, builds a deliverable with LLM-backed agents in a LangGraph pipeline, and delivers it after the founder approves. This version replaces an earlier draft that repeated claims from the project's own docs without checking them.

## How the facts below were obtained

Each figure was read from the source named next to it on 2026-11-12: git history of `origin/main`, a full local `pytest` run (Windows), read-only `gcloud` queries to the Google Cloud project `aistudio-milano`, `gh` for GitHub Actions state, a count-only read of the production Firestore `jobs` collection, and the code or config files named in each row. Anything not checked is marked **not checked**. Descriptions of how things are *meant* to work are labelled as written procedure.

## Numbers

| Measure | Value | Source |
|---------|-------|--------|
| First commit / latest on `main` | 2026-05-23 / 2026-11-12 | git |
| Commits / merged pull requests on `main` | 541 / 108 | git |
| Python files / lines tracked | 404 / 59,889 | git |
| Tests collected | 1,494 across 65 test files | `pytest --collect-only` |
| Test result, full local run | 1,480 passed, 13 failed, 1 skipped | `pytest tests`, Windows |
| Agent definitions in the repo | 24 (`.claude/agents/`) | file count |
| Skills registered in `config/global_settings.json` | 72 | file |
| Delivery rows in the `CLAUDE.md` table | 56 (53 numbered, 3 without a number) | file |
| Audit logs / deliverable folders | 57 / 58 | file count |
| Learning-loop commits on `main` (`learn: …`) | 104, latest 2026-11-12 | git |

**The 13 failing tests:** 11 in `test_retrieval.py`, one in `test_iss002_intent_registry.py`, one in `test_iss007_provider_agnostic_chatbot.py`. For the first retrieval failure the error is a path error from the test's temporary folder; I did not investigate the others.

## Real usage in production (Google Cloud project `aistudio-milano`)

| Fact | Value |
|------|-------|
| Jobs ever stored in Firestore `jobs` | 13, created between 2026-10-09 and 2026-10-16 |
| Where they came from | 11 from the chat IDs configured for founder alerts, 2 from other chats |
| Their status | 4 delivered (three at €0.00, one at €1.90), 2 approved at €5.50, 1 awaiting review, 2 needs_review, 4 classified |
| Requests to the gateway, last 30 days | 10, of which 3 were Telegram webhook calls |
| Requests to the RAG bot service, last 30 days | 964 Telegram webhook calls, the latest on 2026-11-07 |
| Pipeline runs on the worker, last 30 days | 1 (2026-10-16) plus the 10-minute stuck-job sweep |
| Money collected | No payment record exists in the repo. Payment credentials and the VAT number are an open issue (ISS-011). I did not check Stripe or a bank |

The audit logs do not record who a customer was, so the repo cannot tell real customers from the founder testing his own system. The Firestore numbers above are the only direct evidence of outside use: 2 jobs from other chats.

## What is deployed

Verified with `gcloud` on 2026-11-12:

| Item | State |
|------|-------|
| Cloud Run services | `gateway`, `pipeline-worker`, `rag-api` in europe-west8; all three latest revisions deployed 2026-10-09 |
| Cloud Tasks queue `pipeline-runs` | Running (europe-west6) |
| Cloud Scheduler | One job, `sweep-stuck-jobs`, every 10 minutes, enabled; last attempt 2026-11-12 08:50 UTC |
| Firestore | TTL policy on `expire_at` is active |
| Pipeline version in production | v1: the worker has no `PIPELINE_VERSION` setting and v1 is the default; model provider is OpenAI |
| Not deployed | The mail agent (no service, no Scheduler job), the research-digest Scheduler job, the separate admin bot (no admin token on the gateway), the API-key protection of the gateway (no `GATEWAY_API_KEY` on the gateway). The Drive router's Azure side was **not checked** |

The services were last deployed on 2026-10-09. Changes merged after that date are not in these revisions unless redeployed; I did not compare the image contents with the code.

## How a request is processed (as coded)

**Pipeline v1 (the one in production)**, from `deliverables/2026-05-25_016_aistudio-langgraph/graph.py`:

1. `stacy_classify` classifies the request. Its prompt offers 12 product types plus `unknown_product`. A product without a price goes to the founder.
2. `gianni_scope` writes the technical spec.
3. `chiara_implement` builds the deliverable. It uses LLM code generation, with Claude Code as an optional engine that is off by default.
4. Three reviewers run in parallel: `technical_auditor`, `compliance_agent`, `reputation_guardian`.
5. `risk_aggregator` averages their scores (1 to 5). Below 3.5 the run continues; at 3.5 or above it goes to the founder.
6. `stacy_qa` checks the result. A failure returns to Chiara, up to 3 times.
7. `marco_invoice` takes the price from the table, or the price the founder approved. With no price it blocks and escalates.
8. `francesca_deliver` writes the audit log, commits and pushes to git, and sends email on a best-effort basis.

`luigi_escalate` is a human gate: the graph pauses until the founder decides.

**Pipeline v2** (`deliverables/2026-10-16_040_studio-pipeline-v2/`, off by default, not in production) adds: `lorenzo_scan` for prompt injection first, then `devils_advocate`, `financial_controller` and (for remote deploys) `it_staff_advise` before building; a `pricing_gate`; six parallel reviewers (the three above plus `quality_reliability_lead`, `api_product_designer`, `operational_monitor`); a `core_architect` that runs only when a trigger fires; and a `valentina_draft` after delivery. A critical score of 5.0 from any reviewer escalates.

**The "Risk Units" formula is not computed.** The formula `P(event) × impact × blast_radius` and the "2σ" flag appear in agent specs and prompts. The code averages reviewer scores against a fixed threshold; the escalation message it writes says "exceeds 2σ".

**Founder approval over Telegram** (`gateway/admin.py`, `gateway/admin_telegram.py`): buttons Approva, Gratis, Imposta prezzo, Rifiuta; later Invia al cliente, Scarta, Riprova and Riesamina; commands `/pending`, `/approve`, `/prezzo`, `/reject`. Only IDs listed in `ADMIN_TELEGRAM_IDS` (or `NOTIFY_TELEGRAM_CHAT_IDS`) are obeyed. Job state changes go through `transition(job_id, from_status, …)`, which applies an update only if the job is still in the expected status.

## The agent roster

24 agent definitions exist in `.claude/agents/`. They are Claude Code subagent prompts for the founder's development sessions. Only some are also nodes in the production pipeline (v1: Stacy, Gianni, Chiara, Technical Auditor, Compliance Agent, Reputation Guardian, Marco, Francesca, plus the founder gate).

| Group | Agents | Count |
|-------|--------|-------|
| Delivery pipeline | Stacy, Gianni, Chiara, Marco, Francesca | 5 |
| Risk oversight | Technical Auditor, Financial Controller, Operational Monitor, Reputation Guardian, Compliance Agent | 5 |
| Input gateway builders | Pablo, Sofia, Carlos | 3 |
| GitHub research | research-scout, research-analyst, research-curator, research-reporter | 4 |
| V2 review squad | API Product Designer, Core Architect, Devil's Advocate, Quality Reliability Lead | 4 |
| Specialists | Lorenzo, IT Staff, Valentina | 3 |

The founder's `~/.claude/agents/` also holds agents that are not in the repo (Luigi, scout, analyst, curator, reporter, wiki-curator, among others); they are not counted above.

## Products and pricing

- **Price source in code:** the pipeline loads its price table from `config/global_settings.json`. That file has 22 priced entries plus `unknown_product` (null). `CLAUDE.md` lists 19 of them.
- **The three entries only in the settings file:** `white_label_pipeline_license` €1,039.50, `digital_product_publish` €51.45 and `kiosk_deploy_pilot` €0.00.

| Price band | Products in the `CLAUDE.md` table |
|------------|-----------------------------------|
| €0.50 to €3.90 | Email delivery, PDF document, invoice PDF |
| €4.90 to €9.90 | Strategic report, static landing page, weather dashboard, mind dashboard (journal) |
| €14.90 | Calendar integration, micro-syllabus and flashcards, family archivist, Mediterranean meal planner, Niccolò chronicles, bank statement analyst |
| €19.90 to €29.90 | Chatbot app, Streamlit agent deploy, algo trading (€24.90), premium landing page, RAG knowledge base |
| €45.90 | Commercial landing page |

Delivery table, counted from the 56 rows in `CLAUDE.md`:

- 24 numbered rows carry a price and add up to **€329.10 at list price**.
- 25 numbered rows and 3 unnumbered rows are internal tooling at €0.00.
- 3 rows (032, 033, 043) wait for the founder to set a price.
- 1 row (030) has no price recorded.

A "delivered" row is a build recorded in an audit log; it does not mean a customer paid.

## What is built, and what is proven

| Capability | What the repo shows |
|------------|---------------------|
| Telegram intake and founder approval | Running in production (see the jobs above) |
| Pipeline worker, Firestore job store, retention TTL | Running in production |
| Stuck-job sweep | Running; the Scheduler job is enabled and attempted today |
| Privacy notice, erasure, refusal filter | Code exists (`gateway/privacy.py`, `erasure.py`, `safety.py`); deployed with the 2026-10-09 revisions is **not checked** |
| GitHub AI research | Workflow active; last scheduled run 2026-11-12 succeeded (29 successes, 4 failures, 1 cancelled in its history); weekly digest commits on 2026-06-29, 2026-11-06, 2026-11-12 |
| Gateway smoke test | Workflow active; last run 2026-11-12 succeeded (17 successes, 7 cancelled) |
| Bank statement analyst | Tests pass. Delivery 045 records verification on real Credem and ING statements (1,466 movements). A Fineco profile exists; verification on real Fineco statements is not recorded |
| Calendar sentinel | Its README says it was not tried against a real calendar or Telegram; offline tests only |
| Mail agents, Drive router | Built; not deployed on Google Cloud; delivery notes say not proven on real accounts |
| Dispenser with Stripe, WhatsApp, Streamlit form | Code exists (for example `payments/stripe_provider.py`, Twilio signature check); not live: payment credentials are open (ISS-011) and WhatsApp and the form are open (ISS-021) |
| Claude Code build engine | Code exists; off by default (ISS-032) |

## Internal processes and procedures

For each rule: **code** means code or a hook enforces it; **written** means it is a procedure in a document or in `CLAUDE.md` that people and agents are told to follow, with no code that checks it.

| Process | What it says | Enforced by |
|---------|--------------|-------------|
| Price gate | No price means the request is blocked and sent to the founder | code (`stacy_classify`, `marco_invoice`) |
| Founder-only decisions | Approve, price, reject and send only from listed Telegram IDs | code (`gateway/admin.py`) |
| Unknown-intent routing | A map of 17 intents to skills and delivery options | file `process/intent_registry.yaml`, read by the dispenser classifier, the Streamlit gateway app, `learning_loop.py` and tests |
| Tests first, break the task down first | Write a failing test, then implement; decompose non-trivial work | written (`CLAUDE.md`, user instructions) |
| One branch per feature, never push to `main`, auto-merge after the PR | `claude/<slug>` branches; destructive operations, `.env` or credential commits, paused work still ask first | written (`CLAUDE.md`) |
| Done means three artifacts | Audit log, deliverable folder, table row; new pricing in three places | written; `CLAUDE.md` says `scripts/post_delivery_update.py` patches the table |
| Risk review | Five risk agents review each build; GREEN, AMBER or RED; the founder decides ship, ship with conditions or hold; records to be kept in `process/risk_reviews/` | written. That folder does not exist, so no record has been filed. In production only three reviewers run, and they average a score |
| Learning loop | At session end and at confirmed delivery, update settings and lessons; commit automatically when the audit risk score is below 3 | code in `scripts/learning_loop.py` handles two cases only: below 3 it commits, otherwise it prints that approval is pending. The three-tier scheme (3 to 4 notify, 5 or more block) is in `process/learning_loop.md` only |
| Hook promotion thresholds | `security` 1, `external_api_write` 2, `skill_preload` 3, `ui_preference` 5 | configured in settings; only `skill_preload` is read in `learning_loop.py` |
| Mistake log | Every agent logs a mistake at once, reviewed weekly by the founder | written. The log has one entry (ML-001) |
| Session hooks | See next table | code (`.claude/settings.json`), in Claude Code sessions in this repo only |
| Secret scan before commit | Blocks a staged `.env` and known credential patterns | code (`scripts/git-hooks/pre-commit`), switched on by the SessionStart hook |
| Prompt-injection scan | `scripts/injection_detector.py`; `lorenzo_scan` in v2 | code, but production runs v1, which has no scan node |
| Secret scrubbing in run errors | Hides API keys and bot tokens in provider errors and notes | code (`gateway/studio_runner.py`) |

**Hooks in `.claude/settings.json`:**

| Event | Command |
|-------|---------|
| SessionStart | Point git at the pre-commit hooks; copy the repo's agents and skills to `~/.claude` |
| UserPromptSubmit | `scripts.rag.inject_context` (adds retrieved repo chunks); `scripts/agentic_skill_router.py` (adds the framework-skill reminder) |
| PreToolUse on Gmail | `scripts/check_oauth.py --provider gmail` |
| PostToolUse on `mcp__github__push_files` | `learning_loop.py --event delivery_complete` |
| Stop | `learning_loop.py --event session_end`, `delta_collector.py`, `checkpoint_state.py --brief` |

**GitHub Actions state (from `gh workflow list`):**

| Workflow | State | Schedule in the file | Last run |
|----------|-------|----------------------|----------|
| GitHub AI Research | active | Wednesdays 19:17 UTC | 2026-11-12, success |
| Gateway smoke test | active | on changes under `gateway/**` | 2026-11-12, success |
| CI | disabled manually | every push and pull request | 2026-06-11; its last 93 recorded runs all failed. It runs only `tests/test_retrieval.py` as stable tests and six ISS test files as informational |
| Studio Ops | disabled manually | every push | 2026-06-11 |
| Wiki Maintenance | disabled manually | Sundays 10:00 UTC | 2026-06-28 |
| RAG Maintenance | disabled manually | daily 06:00 UTC | 2026-07-02, failure |
| RAG Bootstrap | disabled manually | on push | 2026-06-08 |
| Digital Presence | disabled manually | Mondays 09:00 UTC | 2026-06-29 |
| AI Studio Pipeline | disabled manually | by hand or when an issue is opened | never run |

**Security controls verified in code:** Twilio signature check with HMAC-SHA1 (`gateway/bot_whatsapp.py`); constant-time `X-API-Key` check on `/submit` and `/status` (`gateway/auth.py`); a rate-limit dependency on those routes (`gateway/api.py`); a secret-token header check on the admin Telegram webhook; job retention of 90 days and 30 days for refused jobs (`gateway/retention.py`) with the Firestore TTL active.

**Runbooks (written, in `process/`):** `runbook_cloudrun.md` (deploy in six steps, rollback to the laptop), `runbook_local_telegram_stack.md`, `runbook_mailagent_cloudrun.md`, `runbook_privacy_requests.md` (access and erasure within one month), `runbook_research_digest.md`. Tools: `scripts/check_telegram.py` asks Telegram for `getMe` and `getWebhookInfo` per bot; `scripts/deploy_cloudrun.sh --dry-run` prints commands without running them.

**Other scripts, as their own headers describe them:** `scripts/sync_issues.py` syncs the Open Issues table in `CLAUDE.md` with GitHub issues; `scripts/delta_collector.py` writes a daily file from git log and audit logs and deletes files older than 90 days; `scripts/log_analytics.py` runs a GLM and GBM analysis on delivery data; `scripts/requirements_checker.py` is called by Gianni before scoping; `scripts/suit_manager.py` lists, shows and creates white-label suits (configs S001 and S002 exist); `process/simulation_01_text_input.md` traces one request through the process on paper. Planning documents: a 90-day onboarding plan, a 90-day community roadmap, a profile setup checklist and staff assignments.

## Tech stack

Each item was found in the code or requirements files; the number is how many tracked Python files import it, where that applies.

| Layer | Technology |
|-------|------------|
| Agents | LangGraph (21 files), LangChain (31), deepagents (17), Claude Code subagents |
| Models | OpenAI (31 files; the production worker uses it), Anthropic (5), Ollama (1, the downloads agent) |
| Retrieval | FAISS (`scripts/embed_index.py`) and BM25 (`scripts/retrieve.py`, `scripts/rag/retrieve_repo.py`), ChromaDB and sentence-transformers (Drive router) |
| Apps and APIs | FastAPI (25), Streamlit (31), python-telegram-bot (14), Twilio (2), Stripe (1) |
| Documents and data | fpdf2, pdfplumber, openpyxl |
| Integrations | Google API client (11 files), CalDAV, Microsoft Graph over HTTP (calendar sync), GitHub |
| Google Cloud (verified live) | Cloud Run, Cloud Tasks, Cloud Scheduler, Firestore with TTL, Artifact Registry, Cloud Logging |
| Azure | Deploy script for the Drive router with Key Vault; not checked live |

## Gaps and risks

- **No recorded revenue.** Nothing in the repo shows a collected payment. The €329.10 is list price of delivery-table rows.
- **Little outside use so far.** Thirteen jobs in production, eleven from the founder's own chat.
- **Production is behind the code.** The three Cloud Run services date from 2026-10-09.
- **Automation is mostly switched off.** Seven of nine GitHub workflows are disabled; CI's last 93 runs failed.
- **Tests do not all pass.** 13 of 1,494 fail in a full local run, and the only CI that existed ran a small subset.
- **Written process, little evidence.** No risk-review records, one mistake-log entry, and a learning-loop tier scheme that the code does not implement.
- **Risk scoring is simpler than described.** An average with a fixed threshold, not an actuarial calculation.
- **Production pipeline has no injection scan.** That node exists only in v2.
- **Unit economics not checked.** Marco computes cost and margin per request, but I did not verify any such figures.
- **Docs drift.** For example, the wiki index and some README tables lagged the code until they were synced on 2026-11-12.

## Next steps recorded as open issues

| Issue | Priority | Status in `CLAUDE.md` |
|-------|----------|-----------------------|
| ISS-011 | P1 | Open: Stripe, Twilio, Telegram credentials and VAT number |
| ISS-031 | P1 | Open: deploy the API-key-protected gateway; code ready, not deployed |
| ISS-021 | P2 | Open: Telegram live; WhatsApp and the Streamlit form missing |
| ISS-029 | P2 | Open: separate admin bot, code merged, not deployed |
| ISS-030 | P2 | Open: Drive router needs price, OAuth, image build and deploy |
| ISS-032 | P2 | Open: decide where Claude Code builds may run |
| ISS-025 | P1 | Delivered: the evaluation recommends Payhip over Lemon Squeezy; signing up is not recorded |
