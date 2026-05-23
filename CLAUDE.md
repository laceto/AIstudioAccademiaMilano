# CLAUDE.md

This file provides guidance to Claude Code when working in this repository.

---

## What This Repo Is

**AI Studio Accademia Milano** — a one-human AI enterprise (founder: Luigi Aceto).  
Every user request produces a tangible deployed output: software, PDF, automation, or agent.  
This repo is the operational backbone: agents, skills, pricing, learning loop, and all deliverables.

---

## Active Branch

All development goes to **`claude/digital-communities-guide-a5lBV`**.  
Never push to main directly.

---

## 6-Agent Pipeline

Every request flows through this sequence. Never skip a step.

```
User Input
  ↓
[Stacy]      Intent classification + pricing check (block if unknown_product: null)
  ↓
[Gianni]     Technical scoping, prompt design, risk surface
  ↓
[Chiara]     Implementation (code, content, PDF, template)
  ↓
[Stacy QA]   Output validation (disclaimer check, format, security)
  ↓
[Marco]      Financial: cost + margin + invoice (actuarial background)
  ↓
[Francesca]  Delivery: GitHub push + audit log
```

**Risk agents** (all actuarial background): Technical Auditor, Financial Controller,
Operational Monitor, Reputation Guardian, Compliance Agent.  
Formula: `P(event) × impact × blast_radius` → Risk Units (RU). Flag at 2σ.

---

## Key Files

| File | Purpose |
|------|---------|
| `config/global_settings.json` | Single source of truth: skills, pricing, hooks, MCP, issues |
| `.claude/settings.json` | Hook commands: Stop, PreToolUse, PostToolUse |
| `scripts/learning_loop.py` | Auto-updates settings after every request |
| `scripts/credential_manager.py` | Unified auth store: OAuth tokens + API keys |
| `scripts/embed_index.py` | Build semantic search index over all repo files |
| `scripts/retrieve.py` | Query the index: `python -m scripts.retrieve "query"` |
| `scripts/rag_chat.py` | RAG + GPT synthesis |
| `process/intent_registry.yaml` | All known intents → skills → delivery options |
| `process/audit/` | One YAML-fronted Markdown file per completed request |
| `agents/README.md` | Agent role definitions + actuarial specs |
| `templates/pdf/invoice_standard.py` | `InvoiceTemplate` → valid PDF bytes via fpdf2 |
| `templates/streamlit/chatbot.py` | `ChatbotTemplate(provider, model)` → Streamlit app |
| `wiki/llm/` | Karpathy-style LLM education wiki (7 chapters + code) |
| `deliverables/rag/streamlit_rag_app.py` | Interactive semantic search UI |

---

## Pricing Rules

```json
{
  "static_landing_page": "€9.90",
  "pdf_document":        "€1.90",
  "invoice_pdf":         "€3.90",
  "strategic_report":    "€4.90",
  "chatbot_app":         "€19.90",
  "email_delivery":      "€0.50",
  "rag_knowledge_base":  "€29.90",
  "unknown_product":     null
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

---

## Learning Loop

After every completed request, `scripts/learning_loop.py` runs automatically:

1. Reads latest audit log in `process/audit/`
2. Updates `config/global_settings.json`: new skills, MCP tools, pattern counters
3. Promotes recurring patterns to hooks using **tiered thresholds**:
   - `security` (OAuth/API key skills): threshold = 1
   - `external_api_write` (send/deploy): threshold = 2
   - `skill_preload` (everything else): threshold = 3
4. Auto-commits if risk score < 3; escalates to Luigi if ≥ 3

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
# Run all tests
pytest tests/ -v

# Run a specific issue's tests
pytest tests/test_iss004_templates.py -v
```

Test files follow `tests/test_issNNN_topic.py` naming convention.

---

## RAG Knowledge Base

```bash
# Build index (30s, local sentence-transformers, no API key)
python -m scripts.embed_index

# CLI search
python -m scripts.retrieve "how does Marco price unknown products?"

# RAG + GPT answer (needs OPENAI_API_KEY)
python -m scripts.rag_chat "explain the 6-agent pipeline"

# Streamlit UI
streamlit run deliverables/rag/streamlit_rag_app.py
```

---

## LLM Wiki

`wiki/llm/` — Karpathy-style education, directly connected to studio operations:

- `01_tokenization.md` — BPE, tiktoken, token cost per product
- `02_embeddings.md` — lookup tables, cosine similarity, RAG connection
- `03_attention.md` — Q/K/V, 20-line Python, complexity
- `04_transformer.md` — full architecture, GELU, residuals
- `05_training.md` — pretraining, RLHF, LoRA, RAG vs fine-tune
- `06_inference.md` — temperature, top-k/p, streaming, KV cache
- `07_studio_playbook.md` — model selection, token budgets, prompt engineering
- `code/` — `bpe_minimal.py`, `nano_attention.py`, `sampling_demo.py`

---

## Delivered Requests (Audit Trail)

| ID | Date | Product | Price |
|----|------|---------|-------|
| 001 | 2026-05-23 | Bakery website (HTML/Tailwind + Vercel) | €9.90 |
| 002 | 2026-05-23 | PDF “funziona” + Gmail delivery | €1.90 + €0.50 |
| 003 | 2026-05-23 | Invoice PDF (Marco pricing fix → ISS-001 resolved) | €3.90 |
| 004 | 2026-05-23 | Strategic report: AI startup street monetisation | €4.90 |
| 005 | 2026-05-23 | Streamlit chatbot + OpenAI streaming | €19.90 |
| 006 | 2026-05-23 | RAG system: embed all code + agents, semantic search | €29.90 |

---

## Open Issues

| ID | Priority | Title | Status |
|----|----------|-------|--------|
| ISS-002 | P1 | Build `process/intent_registry.yaml` | OPEN |
| ISS-003 | P2 | Unified credential manager | OPEN |
| ISS-004 | P2 | Build `templates/` library | OPEN |
| ISS-005 | P2 | Tiered thresholds in learning_loop.py | OPEN |
| ISS-006 | P2 | Source citation for advisory outputs | OPEN |
| ISS-007 | P3 | Provider-agnostic chatbot template | OPEN |

---

## Adding a New Skill

1. Implement the code
2. Write tests in `tests/test_issNNN_*.py`
3. Add to `config/global_settings.json` under `skills`
4. Add intent mapping in `intent_to_skill_map`
5. Add price in `pricing` (or `unknown_product: null` until Luigi approves)
6. Write audit log in `process/audit/`
7. The learning loop will promote to a hook if threshold is reached

---

## Router (Legacy — kept for reference)

| Task | Load |
|------|------|
| New request — exploring, planning | `brainstorm-rules.md` |
| Implementing a service, API, automation | `build-rules.md` |
| Creating or extending an AI staff agent profile | `agent-rules.md` |
| Spinning up a new project repo | `project-setup-rules.md` |
| Writing or updating documentation | `docs-rules.md` |

**Every new request starts with brainstorming before implementation.**
