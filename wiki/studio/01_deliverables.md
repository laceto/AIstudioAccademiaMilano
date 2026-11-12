# Deliverables Catalogue

Every shipped product. Auto-updated by `scripts/learning_loop.py` after each delivery.
Last updated: 2026-11-06

| ID | Date | Product | Stack | Price | Path |
|----|------|---------|-------|-------|------|
| 001 | 2026-05-23 | Bakery website | HTML, Tailwind, AlpineJS, Vercel | €9.90 | `deliverables/2026-05-23_001_bakery-website/` |
| 002 | 2026-05-23 | PDF document + Gmail delivery | fpdf2, Gmail API | €2.40 | `deliverables/2026-05-23_002_pdf-email/` |
| 003 | 2026-05-23 | Invoice PDF + Gmail delivery | fpdf2, Gmail API | €3.90 | `deliverables/2026-05-23_003_invoice-pdf-email/` |
| 004 | 2026-05-23 | Strategic report: AI startup monetisation | Markdown, risk agents | €4.90 | `deliverables/2026-05-23_004_strategic-consultation/` |
| 005 | 2026-05-23 | Streamlit chatbot + OpenAI streaming | Streamlit, OpenAI API | €19.90 | `deliverables/2026-05-23_005_chatbot/` |
| 006 | 2026-05-23 | RAG system: semantic search over repo | OpenAI Embeddings, FAISS, Streamlit | €29.90 | `deliverables/rag/` |
| 007 | 2026-05-23 | WhatsApp/Telegram → Calendar sync | Twilio, Telegram Bot, Google/MS/Apple Calendar | €14.90 | `deliverables/2026-05-23_007_calendar-sync/` |
| 008 | 2026-05-23 | GitHub AI Research Department | Scout/Analyst/Curator/Reporter, Streamlit | €0.00 (internal) | `deliverables/github-research/` |
| 009 | 2026-05-23 | LinkedIn Post Generator from GitHub activity | Claude claude-sonnet-4-6, GitHub REST API | €4.90 | `deliverables/2026-05-23_009_linkedin-post-generator/` |
| 010 | 2026-05-23 | Profile Setup & Publishing — 9 platforms | Valentina agent, Twitter/Telegram/Discord/Reddit | €14.90 | `deliverables/2026-05-23_010_profile-setup/` |
| 011 | 2026-05-24 | Milan Weather Dashboard | Streamlit, OpenWeatherMap API | €9.90 | `deliverables/2026-05-24_011_weather-dashboard/` |
| 013 | 2026-05-24 | techa deploy: LangGraph trading agents | LangGraph, TA-Lib, HF Spaces / Cloud Run | €19.90 | `deliverables/2026-05-24_013_techa-deploy/` |
| 014 | 2026-05-24 | Dispenser input v1 | Stripe, Twilio, Telegram Bot, Streamlit | €0.00 (internal infra) | `deliverables/2026-05-24_014_dispenser-input/` |
| 001✓ | 2026-05-24 | Warranty fix: bakery placeholder + form sentinel | JS, SVG | €0.00 (courtesy) | `deliverables/2026-05-23_001_bakery-website/` |
| 034 | 2026-09-16 | deepagents-gcal — deepagents agent + Google Calendar tools (pip package) | deepagents, LangGraph, LangChain, Google Calendar API v3 | €14.90 | `deliverables/2026-09-16_034_deepagents-gcal/` |
| 035 | 2026-10-09 | Cloud Run deploy — gateway + rag-api on `aistudio-milano` (europe-west8), Telegram webhook live | Cloud Run, Cloud Build, Artifact Registry, Secret Manager | €0.00 (internal) | `deliverables/2026-10-09_035_cloud-run-deploy/` |

| 036 | 2026-10-09 | Approval from Telegram + asynchronous pipeline worker — owner alerts (Telegram/e-mail), Firestore job store, approve/price/reject buttons, LangGraph pipeline on a private Cloud Run worker via Cloud Tasks, review before delivery | Cloud Run, Cloud Tasks, Firestore, LangGraph, python-telegram-bot, Secret Manager | €0.00 (internal) | `deliverables/2026-10-09_036_approval-pipeline-worker/` |
| 037 | 2026-10-09 | Data retention, privacy notice and stuck-job recovery — 90-day Firestore TTL with delete protection, `/start` + `/privacy` notice, sweep of jobs stuck in `running` (Cloud Scheduler) | Firestore, Cloud Scheduler, Cloud Run, python-telegram-bot | €0.00 (internal) | `deliverables/2026-10-09_037_retention-privacy-recovery/` |
| 038 | 2026-10-09 | Erase on request and refusal of fraudulent requests — `/cancella` with confirmation card and an erasure record, automatic refusal (phrase filter + model) with RIESAMINA for the customer and Riesamina for the owner, 30-day retention for refusals, `/privacy` in several messages, learning loop promotes hooks only when the script exists | Firestore, python-telegram-bot, Cloud Run | €0.00 (internal) | `deliverables/2026-10-09_038_erasure-and-refusals/` |
| 044 | 2026-10-16 | Lessons learned in the learning loop (idea from Harness²) — `learning_flags.lessons` (cue/lesson/evidence/confidence) merged into global settings, digest `process/lessons_learned.md` read by Gianni and Chiara | Python, PyYAML | €0.00 (internal) | `deliverables/2026-10-16_044_harness-lessons/` |
| 045 | 2026-10-16 | Bank statement analyst — Credem/ING PDF statements → movements (debit/credit read from the column position, row stripes as movement bounds), balance reconciliation, YAML rules with a personal layer, transfers excluded from totals, quarterly Excel; verified on 5 real Credem and 4 real ING statements | Python, pdfplumber, openpyxl | €14.90 | `deliverables/2026-10-16_045_bank-statement-analyst/` |
| 046 | 2026-11-05 | Gateway smoke test (GitHub Action) — simulated project request to `/submit`: `local` job (gateway in the runner, worker on → `needs_review`) on every push/PR touching `gateway/**`, `deployed` job (Cloud Run: health, submit, status) on manual dispatch | GitHub Actions, FastAPI, Python stdlib | €0.00 (internal) | `deliverables/2026-11-05_046_gateway-smoke-action/` |
| 047 | 2026-11-05 | Gateway protected with an API key — `POST /submit` and `GET /status` need `X-API-Key` (fail closed with 503 when no key is set), showcase order buttons link to the Telegram bot, deploy keeps the key in Secret Manager | FastAPI, Cloud Run, Secret Manager | €0.00 (internal) | `deliverables/2026-11-05_047_protect-gateway/` |
| 048 | 2026-11-05 | Smoke test all the way to a deliverable — `scripts/gateway_deliver.py` approves the smoke job as Luigi would and runs it through the real pipeline worker in the runner; deliverable, `result.json` and `steps.txt` as the artifact `deliverable` and in the run Summary (opt-in `run_pipeline`) | GitHub Actions, LangGraph, FastAPI | €0.00 (internal) | `deliverables/2026-11-05_048_smoke-deliverable/` |
| 049 | 2026-11-05 | GitHub research also scans trending — `scripts/github_research/trending.py` reads github.com/trending, keeps AI repos, enriches them via the REST API; trending bucket in the Scout, growth from the current pace, "Trending on GitHub" report section, trending note in Gianni's digest | Python, GitHub REST API | €0.00 (internal) | `deliverables/2026-11-05_049_research-trending/` |
| 050 | 2026-11-06 | Chiara builds with Claude Code — with `CHIARA_ENGINE=claude_code`, code products are built by the Claude Code CLI headless (several files, tests written and run), packed into one text bundle (`scripts/unpack_bundle.py` restores the files); clean env, separate `builder` user, pytest-only Bash, budget and timeout; falls back to the usual strategy on any error; off by default | LangGraph, Claude Code CLI, Cloud Run | €0.00 (internal) | `deliverables/2026-11-06_050_chiara-claude-code/` |
## Revenue Summary

| Status | Amount |
|--------|--------|
| Invoiced (billable requests 001–013) | €135.40 |
| R&D / internal / courtesy (008, 014, warranty) | €0.00 |
| Collected | €0.00 _(blocked: ISS-011 Partita IVA pending)_ |
