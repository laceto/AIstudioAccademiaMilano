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
Naming convention: `claude/<slug>` (e.g. `claude/calendar-sync`, `claude/readme-review`).  
The branch `claude/digital-communities-guide-a5lBV` is legacy — do not use it.

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

**Risk agents** (all actuarial background): Technical Auditor, Financial Controller,
Operational Monitor, Reputation Guardian, Compliance Agent.  
Formula: `P(event) x impact x blast_radius` -> Risk Units (RU). Flag at 2sigma.

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
| `scripts/rag_chat.py` | RAG + GPT synthesis |
| `scripts/github_research/main.py` | GitHub AI Research CLI (Scout->Analyst->Curator->Reporter) |
| `process/intent_registry.yaml` | All known intents -> skills -> delivery options |
| `process/audit/` | One YAML-fronted Markdown file per completed request |
| `agents/README.md` | Agent role definitions + actuarial specs |
| `agents/research/README.md` | GitHub Research Department spec |
| `templates/pdf/invoice_standard.py` | `InvoiceTemplate` -> valid PDF bytes via fpdf2 |
| `templates/streamlit/chatbot.py` | `ChatbotTemplate(provider, model)` -> Streamlit app |
| `wiki/llm/` | Karpathy-style LLM education wiki (7 chapters + code) |
| `deliverables/rag/streamlit_rag_app.py` | Interactive semantic search UI |
| `deliverables/github-research/streamlit_research_app.py` | GitHub AI Research dashboard |

---

## Pricing Rules

```json
{
  "static_landing_page":  "9.90",
  "pdf_document":         "1.90",
  "invoice_pdf":          "3.90",
  "strategic_report":     "4.90",
  "chatbot_app":          "19.90",
  "email_delivery":       "0.50",
  "rag_knowledge_base":   "29.90",
  "calendar_integration": "14.90",
  "weather_dashboard":    "9.90",
  "unknown_product":      null
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
python -m scripts.embed_index                         # build index (~30s local)
python -m scripts.retrieve "how does Marco price unknown products?"
python -m scripts.rag_chat "explain the 6-agent pipeline"  # needs OPENAI_API_KEY
streamlit run deliverables/rag/streamlit_rag_app.py
```

---

## GitHub AI Research Department

```bash
pip install -r requirements-research.txt
export GITHUB_TOKEN=ghp_...     # optional, 60->5000 req/h
python scripts/github_research/main.py --topics llm rag ai-agents --min-stars 200
streamlit run deliverables/github-research/streamlit_research_app.py
```

Agents: **Scout** (search) -> **Analyst** (score) -> **Curator** (dedup+categorise) -> **Reporter** (digest+dashboard)
See `agents/research/README.md`.

---

## LLM Wiki

`wiki/llm/` — Karpathy-style, 7 chapters + runnable code examples:

- `01_tokenization.md` — BPE, tiktoken, token cost per product
- `02_embeddings.md` — lookup tables, cosine similarity, RAG connection
- `03_attention.md` — Q/K/V, 20-line Python, complexity
- `04_transformer.md` — full architecture, GELU, residuals
- `05_training.md` — pretraining, RLHF, LoRA, RAG vs fine-tune
- `06_inference.md` — temperature, top-k/p, streaming, KV cache
- `07_studio_playbook.md` — model selection, token budgets, prompt engineering
- `code/` — `bpe_minimal.py`, `nano_attention.py`, `sampling_demo.py`

---

## Delivered Requests

| ID | Date | Product | Price |
|----|------|---------|-------|
| 001 | 2026-05-23 | Bakery website (HTML/Tailwind + Vercel) | 9.90 |
| 002 | 2026-05-23 | PDF "funziona" + Gmail delivery | 2.40 |
| 003 | 2026-05-23 | Invoice PDF (INV-003 Mario Rossi) + Gmail delivery | 3.90 |
| 004 | 2026-05-23 | Strategic report: AI startup street monetisation | 4.90 |
| 005 | 2026-05-23 | Streamlit chatbot + OpenAI streaming | 19.90 |
| 006 | 2026-05-23 | RAG system: embed all code + agents | 29.90 |
| 007 | 2026-05-23 | WhatsApp/Telegram -> Apple/Outlook/Gmail calendar sync | 14.90 |
| 008 | 2026-05-23 | GitHub AI Research Department (Scout/Analyst/Curator/Reporter) | 0.00 |
| 009 | 2026-05-23 | LinkedIn Post Generator from GitHub activity (Claude claude-sonnet-4-6) | 4.90 |
| 010 | 2026-05-23 | Profile Setup & Publishing — bio + first post for 9 platforms | 14.90 |
| 011 | 2026-05-24 | Milan Weather Dashboard (Streamlit + OpenWeatherMap) | 9.90 |
| 013 | 2026-05-24 | techa Streamlit deploy (LangGraph trading agents + TA-Lib, HF Spaces target) | 19.90 |

---

## Open Issues

| ID | Priority | Title | Status |
|----|----------|-------|--------|
| ISS-002 | P1 | Build `process/intent_registry.yaml` | OPEN |
| ISS-003 | P2 | Unified credential manager | OPEN |
| ISS-004 | P2 | Build `templates/` library (InvoiceTemplate, ChatbotTemplate) | OPEN |
| ISS-005 | P2 | Tiered thresholds in learning_loop.py | OPEN |
| ISS-006 | P2 | Source citation for advisory outputs | OPEN |
| ISS-007 | P3 | Provider-agnostic chatbot template | OPEN |
| ISS-008 | P2 | RAG retrieval system | DELIVERED |
| ISS-009 | P3 | Schedule GitHub Research runs (cron + digest commit) | OPEN |
| ISS-010 | P2 | Add `hosting_target` required field to requirements gate for `*_deploy_*` intents (HF Spaces / Render / Docker / local) | OPEN |
