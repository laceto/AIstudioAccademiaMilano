# CLAUDE.md

This file provides guidance to Claude Code when working in this repository.

---

## What This Repo Is

**AI Studio Accademia Milano** — a one-human AI enterprise (founder: Luigi Aceto).  
Every user request produces a tangible deployed output: software, PDF, automation, or agent.  
This repo is the operational backbone: agents, skills, pricing, learning loop, and all deliverables.

---

## Active Branch

Create a **fresh branch from main** for every feature. Never push to main directly.  
Naming convention: `claude/<slug>` (e.g. `claude/calendar-sync`, `claude/new-feature`).

---

## 6-Agent Pipeline

Every request flows through this sequence. Never skip a step.

```
User Input
  |
  v
[Stacy]      Intent classification + pricing check (block if unknown_product: null)
  |
  v
[Gianni]     Technical scoping, stack selection, risk surface
  |
  v
[Chiara]     Implementation (code, content, PDF, template)
  |
  v
[Stacy QA]   Output validation (disclaimer check, format, security)
  |
  v
[Marco]      Financial: cost + margin + invoice (actuarial background)
  |
  v
[Francesca]  Delivery: GitHub push + audit log
```

**Parallel agents:**
- **Risk agents** (actuarial): Technical Auditor, Financial Controller, Operational Monitor, Reputation Guardian, Compliance Agent — see `agents/risk/`
- **Valentina** (publishing): triggered by Francesca on new deliverable, generates platform content, publishes with confirmation gate — see `agents/valentina.md`
- **Research Department**: Scout → Analyst → Curator → Reporter — see `agents/research/`

---

## Key Files

| File | Purpose |
|------|--------|
| `config/global_settings.json` | Single source of truth: skills, pricing, hooks, MCP, issues |
| `.claude/settings.json` | Hook commands: Stop, PreToolUse, PostToolUse |
| `scripts/learning_loop.py` | Auto-updates settings after every request |
| `scripts/credential_manager.py` | Unified auth store: OAuth tokens + API keys |
| `scripts/embed_index.py` | Build semantic search index over all repo files |
| `scripts/retrieve.py` | Query the index: `python -m scripts.retrieve "query"` |
| `scripts/github_research/main.py` | GitHub AI Research CLI (Scout→Analyst→Curator→Reporter) |
| `process/intent_registry.yaml` | All known intents → skills → delivery options |
| `process/audit/` | One YAML-fronted Markdown file per completed request |
| `process/profile_setup_checklist.md` | Per-platform signup URLs + status tracker (Valentina) |
| `process/execution_roadmap_90_days.md` | 90-day community launch roadmap |
| `agents/README.md` | All agent role definitions |
| `agents/valentina.md` | Valentina: Profile Setup & Publishing Agent |
| `agents/risk/README.md` | AI Risk Management Department (5 agents) |
| `agents/research/README.md` | GitHub Research Department spec |
| `templates/pdf/invoice_standard.py` | `InvoiceTemplate` → valid PDF bytes via fpdf2 |
| `templates/streamlit/chatbot.py` | `ChatbotTemplate(provider, model)` → Streamlit app |
| `ProjectRegistry.md` | Central registry of all deliverables and internal systems |
| `projects/README.md` | Git submodule convention for future standalone repos |
| `framework/ai_risk_management_team.md` | Risk team architecture |
| `community/community_map.md` | Community funnel + interaction model |
| `community/digital_platforms.md` | Platform matrix (purpose, automation, outputs) |
| `deliverables/2026-05-23_008_algo-trading/` | SMA crossover bot, Alpaca paper trading |
| `deliverables/2026-05-23_009_linkedin-post-generator/` | GitHub activity → LinkedIn post (Claude) |
| `deliverables/2026-05-23_010_profile-setup/` | Valentina: bio + first post + publish pipeline |
| `wiki/llm/` | Karpathy-style LLM education wiki (7 chapters + code) |

---

## Pricing Rules

```json
{
  "static_landing_page":    "9.90",
  "pdf_document":           "1.90",
  "invoice_pdf":            "3.90",
  "strategic_report":       "4.90",
  "linkedin_post":          "4.90",
  "chatbot_app":            "19.90",
  "algo_trading_bot":       "24.90",
  "email_delivery":         "0.50",
  "rag_knowledge_base":     "29.90",
  "calendar_integration":   "14.90",
  "profile_setup_automation": "14.90",
  "unknown_product":        null
}
```

**Marco must block and escalate to Luigi if `unknown_product: null`.** Never guess.

---

## Security Constraints (Non-Negotiable)

- OAuth tokens used for single session only — never stored or logged
- API keys in Streamlit Secrets or env vars — never in code
- `unknown_product: null` blocks delivery until Luigi approves price
- Credential manager (`scripts/credential_manager.py`) TTL: session-scoped
- Advisory outputs must include disclaimer at top or bottom (validated by `validate_advisory_output()`)
- Apple Calendar: app-specific password only (generate at appleid.apple.com) — main Apple ID password never used
- Twilio webhook: HMAC-SHA1 signature validation active in production
- Google `credentials.json` and `token.json` kept local, never committed
- Alpaca trading: `paper=True` hardcoded — never change without explicit Luigi approval
- Valentina publishing: confirmation gate required before every auto-publish — Luigi approves all posts

---

## Learning Loop

After every completed request, `scripts/learning_loop.py` runs automatically:

1. Reads latest audit log in `process/audit/`
2. Updates `config/global_settings.json`: new skills, MCP tools, pattern counters
3. Promotes recurring patterns to hooks using **tiered thresholds**:
   - `security` (OAuth/API key skills): threshold = 1
   - `external_api_write` (send/deploy): threshold = 2
   - `skill_preload` (everything else): threshold = 3
4. Auto-commits if risk score < 3; escalates to Luigi if >= 3

---

## Audit Log Format

Every delivery creates `process/audit/YYYY-MM-DD_NNN_slug.md` with YAML block:

```yaml
request_id: "NNN"
date: "YYYY-MM-DD"
intent: <intent_name>
outcome: success | failure
agents_invoked: [{name, role, action, duration_sec, status}]
skills_used: [list]
learning_flags:
  new_skills: [list]
  new_mcp: [list]
  risk_score: 1-5
```

---

## Testing Approach (TDD)

Write failing tests first. Then implement. Never the other way.

```bash
pytest tests/ -v
pytest tests/test_iss004_templates.py -v
```

Test files: `tests/test_issNNN_topic.py`

---

## RAG Knowledge Base

```bash
python -m scripts.embed_index
python -m scripts.retrieve "how does Marco price unknown products?"
streamlit run deliverables/rag/streamlit_rag_app.py
```

---

## GitHub AI Research Department

```bash
export GITHUB_TOKEN=ghp_...     # optional, 60→5000 req/h
python scripts/github_research/main.py --topics llm rag ai-agents --min-stars 200
streamlit run deliverables/github-research/streamlit_research_app.py
```

Scheduled: daily S-tier alert (07:00 UTC) + weekly digest (Mon 08:00 UTC) via `.github/workflows/research_schedule.yml`.

---

## Delivered Requests

| ID | Date | Product | Price |
|----|------|---------|-------|
| 001 | 2026-05-23 | Bakery website (HTML/Tailwind + Vercel) | €9.90 |
| 002 | 2026-05-23 | PDF “funziona” + Gmail delivery | €2.40 |
| 003 | 2026-05-23 | Invoice PDF (INV-003 Mario Rossi) + Gmail delivery | €3.90 |
| 004 | 2026-05-23 | Strategic report: AI startup street monetisation | €4.90 |
| 005 | 2026-05-23 | Streamlit chatbot + OpenAI streaming | €19.90 |
| 006 | 2026-05-23 | RAG system: embed all code + agents | €29.90 |
| 007 | 2026-05-23 | WhatsApp/Telegram → Apple/Outlook/Gmail calendar sync | €14.90 |
| 008 | 2026-05-23 | Algo trading bot (SMA crossover, Alpaca paper) | €24.90 |
| 009 | 2026-05-23 | LinkedIn post generator from GitHub activity | €4.90 |
| 010 | 2026-05-23 | Profile setup & publishing automation (Valentina) | €14.90 |

---

## Issues

| ID | Priority | Title | Status |
|----|----------|-------|--------|
| ISS-002 | P1 | Build `process/intent_registry.yaml` | ✅ DELIVERED |
| ISS-003 | P2 | Unified credential manager | ✅ DELIVERED |
| ISS-004 | P2 | Build `templates/` library (InvoiceTemplate, ChatbotTemplate) | ✅ DELIVERED |
| ISS-005 | P2 | Tiered thresholds in learning_loop.py | ✅ DELIVERED |
| ISS-006 | P2 | Source citation for advisory outputs | ✅ DELIVERED |
| ISS-007 | P3 | Provider-agnostic chatbot template | ✅ DELIVERED |
| ISS-008 | P2 | RAG retrieval system | ✅ DELIVERED |
| ISS-009 | P3 | Schedule GitHub Research runs (cron + digest commit) | ✅ DELIVERED |
