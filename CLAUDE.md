# CLAUDE.md — Studio Router

This file is the **primary router** for every Claude session in this repo.  
Read Step 1–3 before touching any code. Reference sections follow.

---

## STEP 1 — CLASSIFY THE REQUEST

Map the user request to an intent, then look it up in the table below.  
If the intent is not in the table → `unknown_product: null` → **block, escalate to Luigi**.

| Intent keyword(s) | Product key | Price | Skills to preload |
|-------------------|-------------|-------|-------------------|
| landing page, sito statico | `static_landing_page` | 9.90 | — |
| landing page premium | `premium_landing_page` | 29.90 | — |
| landing page commerciale | `commercial_landing_page` | 45.90 | — |
| PDF, documento | `pdf_document` | 1.90 | — |
| fattura, invoice | `invoice_pdf` | 3.90 | `templates/pdf/invoice_standard.py` |
| report strategico | `strategic_report` | 4.90 | — |
| chatbot, streamlit chat | `chatbot_app` | 19.90 | `templates/streamlit/chatbot.py` |
| email delivery | `email_delivery` | 0.50 | — |
| RAG, knowledge base, embeddings | `rag_knowledge_base` | 29.90 | `langchain-rag`, `langgraph-fundamentals` |
| calendario, calendar sync | `calendar_integration` | 14.90 | — |
| meteo, weather dashboard | `weather_dashboard` | 9.90 | — |
| deploy streamlit, agent deploy | `agent_deploy_streamlit` | 19.90 | `langgraph-subagents` |
| trading, algo trading, bot | `algo_trading` | 24.90 | `langgraph-fundamentals` |
| mind dashboard, journal | `mind_dashboard_journal` | 9.90 | — |
| syllabus, flashcard | `micro_syllabus_flashcards` | 14.90 | — |
| family archivist | `family_archivist` | 14.90 | — |
| meal planner, ricette | `mediterranean_meal_planner` | 14.90 | — |
| niccolò chronicles, time capsule | `niccolo_chronicles` | 14.90 | — |
| qualsiasi altro | `unknown_product` | **null** | **BLOCK** |

---

## STEP 2 — AGENTIC FRAMEWORK GATE

If the request involves **LangGraph, LangChain, multi-agent, o pipeline agentiche** → invoke `/agentic-router` **before** scrivere codice.

| Trigger | Skills obbligatorie |
|---------|---------------------|
| LangGraph / StateGraph / Send dispatch | `langgraph-fundamentals`, `langgraph-dynamic-parallelism` |
| Subagenti / nested agents | `langgraph-subagents`, `deep-agents-orchestration` |
| Persistence / checkpointing | `langgraph-persistence` |
| Human-in-the-loop | `langgraph-human-in-the-loop` |
| LangChain chains / RAG | `langchain-fundamentals`, `langchain-rag` |
| Memory cross-session | `deep-agents-memory` |
| Orchestrazione generica | `deep-agents-core` |

> `scripts/agentic_skill_router.py` si attiva su ogni `UserPromptSubmit` e inietta questo reminder automaticamente. Non saltare mai l'invocazione dello skill.

---

## STEP 3 — ESEGUI LA PIPELINE (6 agenti, in ordine)

```
User Input
  │
  ▼
[Stacy]      Classifica intent + pricing check → blocca se unknown_product: null
  │
  ▼
[Gianni]     Scoping tecnico, stack, superficie di rischio
  │
  ▼
[Chiara]     Implementazione (codice, PDF, template, contenuto)
  │
  ▼
[Stacy QA]   Validazione output (disclaimer, formato, sicurezza)
  │
  ▼
[Marco]      Finance: costo + margine + fattura (background attuariale)
  │
  ▼
[Francesca]  Delivery: push GitHub + audit log
```

**Risk agents** (tutti background attuariale): Technical Auditor, Financial Controller,  
Operational Monitor, Reputation Guardian, Compliance Agent.  
Formula: `P(event) × impact × blast_radius` → Risk Units (RU). Flag a 2σ.

---

## STEP 4 — DELIVERY CHECKLIST

Prima di chiudere ogni task:

- [ ] Audit log creato in `process/audit/YYYY-MM-DD_NNN_slug.md`
- [ ] Cartella `deliverables/YYYY-MM-DD_NNN_slug/` presente
- [ ] Riga aggiunta nella tabella **Delivered Requests** sotto
- [ ] Se nuova pricing → aggiornata anche in `config/global_settings.json`
- [ ] Branch `claude/<slug>` pushato, PR aperta e mergiata via GitHub MCP

**Pre-push (10 sec):** `ls process/audit/ | tail -3` → NNN corretto → `grep "| $NNN " CLAUDE.md` → esattamente una riga.

---

---

# REFERENCE

Le sezioni seguenti sono consultazione, non routing. Non saltarle per pigrizia.

---

## Active Branch

Crea un **branch fresco da main** per ogni feature. Mai pushare su main direttamente.  
Convention: `claude/<slug>` (es. `claude/calendar-sync`).  
Il branch `claude/digital-communities-guide-a5lBV` è legacy — non usarlo.

**Auto-commit e merge a task completato (regola permanente).** Commita sul feature branch, pusha, apri PR su `main`, mergela via GitHub MCP — senza chiedere conferma a ogni passo. Eccezioni che richiedono ancora conferma: operazioni distruttive (`git reset --hard`, `git push --force`, cancellazione branch), commit che toccano `.env`/credenziali, lavoro che l'utente ha esplicitamente messo in pausa.

---

## Cross-Platform Hook Convention

Hook in `.claude/settings.json` girano in entrambi gli ambienti:
- **Windows locale** (macchina di Luigi, Git Bash) — `C:\Users\l_ace\Desktop\projects\...`
- **Linux remoto** (container Claude Code on the web) — `/home/user/<repo>`

**Mai hardcodare path assoluti.** Usa:
- `$CLAUDE_PROJECT_DIR` — root del repo
- `$HOME/.claude` — config dir globale di Claude

**Propagazione globale:** replica la convention in `~/.claude/CLAUDE.md` (memoria globale di Luigi) così vale per ogni progetto futuro.

---

## Security Constraints (Non-Negotiable)

- OAuth token: solo sessione corrente — mai salvati o loggati
- API key: in Streamlit Secrets o env var — mai nel codice
- `unknown_product: null` blocca la delivery finché Luigi approva il prezzo
- Credential manager TTL: scoped alla sessione (`scripts/credential_manager.py`)
- Output advisory: disclaimer obbligatorio (validato da `validate_advisory_output()`)
- Apple Calendar: solo app-specific password (appleid.apple.com) — mai password principale
- Twilio webhook: HMAC-SHA1 attivo in produzione
- Google `credentials.json` e `token.json`: locali, mai committati
- **Pre-commit secret scan** (`scripts/git-hooks/pre-commit`): blocca `.env` staged e pattern di credenziali noti. Auto-attivato dal hook `SessionStart` in `.claude/settings.json` (`git config core.hooksPath scripts/git-hooks`). Bypass solo con `--no-verify` per falsi positivi confermati.

---

## Pricing Rules

```json
{
  "static_landing_page":       "9.90",
  "premium_landing_page":      "29.90",
  "commercial_landing_page":   "45.90",
  "pdf_document":              "1.90",
  "invoice_pdf":               "3.90",
  "strategic_report":          "4.90",
  "chatbot_app":               "19.90",
  "email_delivery":            "0.50",
  "rag_knowledge_base":        "29.90",
  "calendar_integration":      "14.90",
  "weather_dashboard":         "9.90",
  "agent_deploy_streamlit":    "19.90",
  "algo_trading":              "24.90",
  "mind_dashboard_journal":    "9.90",
  "micro_syllabus_flashcards": "14.90",
  "family_archivist":          "14.90",
  "mediterranean_meal_planner":"14.90",
  "niccolo_chronicles":        "14.90",
  "unknown_product":           null
}
```

**Marco blocca ed escala a Luigi se `unknown_product: null`.** Mai indovinare.

---

## Key Files

| File | Scopo |
|------|-------|
| `config/global_settings.json` | Single source of truth: skills, pricing, hooks, MCP, issues |
| `pytest.ini` | `pythonpath = .` — rende `scripts/` importabile in CI e locale |
| `config/accounts_registry.yaml` | Tutti gli account platform: URL, status, credential readiness |
| `.claude/settings.json` | Hook: Stop, PreToolUse, PostToolUse, UserPromptSubmit (RAG injection) |
| `credentials/registry.md` | Guida step-by-step per tutte le credenziali |
| `.env.example` | Template variabili d'ambiente — copia in `.env` e compila |
| `scripts/learning_loop.py` | Auto-aggiorna settings dopo ogni request |
| `scripts/git-hooks/pre-commit` | Blocca `.env` + pattern segreti noti |
| `scripts/post_delivery_update.py` | Post-commit: crea audit stub, patcha tabella CLAUDE.md |
| `scripts/digital_presence_pipeline.py` | Bridge D009+D010: GitHub activity → post → multi-platform |
| `scripts/rag/embed_repo.py` | Indicizza tutti i file via kitai batch + FAISS |
| `scripts/rag/retrieve_repo.py` | Retrieval ibrido BM25+FAISS |
| `scripts/rag/inject_context.py` | Hook UserPromptSubmit — inietta top-5 chunk prima di ogni risposta |
| `scripts/rag/synthesize.py` | Sintesi async via kitai.batch (50% più economico, output Pydantic) |
| `scripts/github_research/main.py` | GitHub AI Research CLI (Scout→Analyst→Curator→Reporter) |
| `process/intent_registry.yaml` | Tutti gli intent noti → skills → opzioni di delivery |
| `process/audit/` | Un file Markdown con YAML frontmatter per ogni request completata |
| `agents/README.md` | Definizioni dei ruoli agente + spec attuariali |
| `agents/rag/README.md` | RAG Team spec |
| `agents/research/README.md` | GitHub Research Department spec |
| `agents/input_gateway/README.md` | Input Gateway Team spec (Pablo, Sofia, Carlos) |
| `templates/pdf/invoice_standard.py` | `InvoiceTemplate` → PDF bytes via fpdf2 |
| `templates/streamlit/chatbot.py` | `ChatbotTemplate(provider, model)` → Streamlit app |
| `wiki/llm/` | Wiki LLM stile Karpathy (7 capitoli + codice) |
| `deliverables/rag/streamlit_rag_app.py` | UI ricerca semantica interattiva |
| `deliverables/github-research/streamlit_research_app.py` | GitHub AI Research dashboard |
| `config/suits/` | Config white-label — S001 = origine, S002+ = repliche |
| `config/suits/suit_schema.yaml` | Schema canonico per tutti i campi suit |
| `scripts/suit_manager.py` | CLI: `list`, `show`, `create` suit; valida contro suit_schema.yaml |
| `scripts/run_pipeline_cli.py` | Entrypoint CLI per la pipeline a 6 agenti |
| `scripts/log_analytics.py` | Metriche di delivery + revenue analytics dagli audit log |
| `scripts/chat_analysis/` | Pipeline chat→RSS: parser WhatsApp/Claude, analyzer, RSS 2.0 + OPML |
| `aziende-fabrizia/` | Verticale Fabrizia — `diabetologia-endocrinologia/` con 4 deliverable |
| `.github/workflows/pipeline.yml` | GitHub Actions: trigger pipeline via `workflow_dispatch` o issue |
| `.github/workflows/rag-bootstrap.yml` | GitHub Actions: rebuild FAISS index su push |

---

## Audit Log Format

Ogni delivery crea `process/audit/YYYY-MM-DD_NNN_slug.md`:

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

## Delivery ID Policy

1. **Il filename dell'audit log è l'ID canonico.** Formato: `process/audit/YYYY-MM-DD_NNN_slug.md`.
2. **ID globalmente unici e monotòni.** Next ID = max(NNN) + 1 su tutti gli audit log.
3. **Tre artefatti devono coesistere** per considerare una delivery "done": audit log + cartella deliverable + riga nella tabella.
4. **Nuova pricing → aggiornata in 3 posti nello stesso commit:** audit log, tabella CLAUDE.md, `config/global_settings.json`.
5. **Tooling interno senza audit log numerato** usa ID `—` nella tabella, path `deliverables/<slug>/`.

---

## Learning Loop

**`scripts/post_delivery_update.py`** — hook `post-commit`:
1. Rileva nuove cartelle `deliverables/YYYY-MM-DD_NNN_slug/` senza audit log
2. Crea stub audit log in `process/audit/`
3. Aggiorna `config/global_settings.json` + nuove skills
4. Patcha la tabella Delivered Requests

**`scripts/learning_loop.py`** — hook `Stop`:
```
python scripts/learning_loop.py \
  --event session_end \
  --audit-dir process/audit \
  --settings config/global_settings.json \
  --claude-dir C:\Users\l_ace\.claude
```
Soglie promozione hook: `security` = 1, `external_api_write` = 2, `skill_preload` = 3.  
Auto-commit se risk score < 3; escala a Luigi se ≥ 3.

---

## Testing (TDD)

Scrivi prima il test fallente. Poi implementa. Mai il contrario.

```bash
pytest tests/ -v
pytest tests/test_iss004_templates.py -v
```

---

## RAG Knowledge Base

```bash
python -m scripts.embed_index
python -m scripts.retrieve "how does Marco price unknown products?"
python -m scripts.rag_chat "explain the 6-agent pipeline"
streamlit run deliverables/rag/streamlit_rag_app.py
```

---

## GitHub AI Research Department

```bash
pip install -r requirements-research.txt
export GITHUB_TOKEN=ghp_...
python scripts/github_research/main.py --topics llm rag ai-agents --min-stars 200
streamlit run deliverables/github-research/streamlit_research_app.py
```

Scout → Analyst → Curator → Reporter. Vedi `agents/research/README.md`.

---

## LLM Wiki

`wiki/llm/` — 7 capitoli + codice runnable:

- `01_tokenization.md` — BPE, tiktoken, costo token per prodotto
- `02_embeddings.md` — lookup table, cosine similarity, RAG
- `03_attention.md` — Q/K/V, Python 20 righe, complessità
- `04_transformer.md` — architettura completa, GELU, residuals
- `05_training.md` — pretraining, RLHF, LoRA, RAG vs fine-tune
- `06_inference.md` — temperature, top-k/p, streaming, KV cache
- `07_studio_playbook.md` — selezione modello, budget token, prompt engineering
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
| 008 | 2026-05-23 | Algo Trading Bot — Alpaca paper (paper=True hardcoded), SMA(20/50)+RSI, 5% position cap, Streamlit/Plotly dashboard | 24.90 |
| 009 | 2026-05-23 | LinkedIn Post Generator from GitHub activity | 4.90 |
| 010 | 2026-05-23 | Profile Setup & Publishing — bio + first post for 9 platforms | 14.90 |
| 011 | 2026-05-24 | Milan Weather Dashboard (Streamlit + OpenWeatherMap) | 9.90 |
| 013 | 2026-05-24 | techa Streamlit deploy (LangGraph trading agents + TA-Lib, HF Spaces / Cloud Run) | 19.90 |
| —   | 2026-05-23 | GitHub AI Research Department (Scout/Analyst/Curator/Reporter) — internal tooling | 0.00 |
| 014 | 2026-05-24 | Dispenser input v1 — QR/Streamlit form, Stripe, WhatsApp+Telegram delivery | 0.00 (internal) |
| 015 | 2026-05-25 | Logo Generator — circle/square/minimal styles | 0.00 (internal) |
| 016 | 2026-05-25 | AI Studio LangGraph assistant — multi-agent graph con nodi dipartimento paralleli | 0.00 (internal) |
| 017 | 2026-05-25 | Lawyer LangGraph + Mindful Bot — white-label legal + psychology entry product | 0.00 (internal) |
| 018 | 2026-05-25 | SOAP Note Generator — psychology vertical Streamlit app (pilota Diletta) | 0.00 (internal) |
| 019 | 2026-05-25 | Studio Digital Twin — LangGraph parallel simulation della pipeline a 6 agenti | 0.00 (internal) |
| 020 | 2026-05-26 | Mind Dashboard — daily AI briefing da testo journal grezzo | 9.90 |
| 021 | 2026-05-26 | Micro-Syllabus & Flashcard Generator — piano 7 giorni + 10 carte Anki (OpenAI gpt-4o) | 14.90 |
| 022 | 2026-05-26 | Family Archivist — HTML single-file per pensionati, voice/text → story_archive.md | 14.90 |
| 023 | 2026-05-26 | Mediterranean Meal Planner — menu settimanale + lista spesa (OpenAI gpt-4o) | 14.90 |
| 024 | 2026-05-26 | The Niccolò Chronicles — WhatsApp time-capsule → Niccolo_Age_5_Month_<Month>.md | 14.90 |
| 025 | 2026-05-27 | Chat-to-Insights RSS Pipeline — parser sessioni Claude + WhatsApp + audit log | 0.00 (internal) |
| 026 | 2026-05-27 | Trading Agent Team Dashboard + API — 4 agenti, JSON store, Streamlit, FastAPI | 24.90 |
| 027 | 2026-05-27 | DIY Electrical Brainstorm — affinity groups + API landscape cantina 3×4 | 4.90 |
| 028 | 2026-05-27 | Team Showcase — Streamlit app del full coding team | 0.00 (internal) |
| 029 | 2026-06-03 | Reinsurance Branch Office — LangGraph 3-workflow (claim/treaty/report) + Streamlit | 0.00 (internal) |
| —   | 2026-06-05 | Input Gateway — FastAPI `/submit`, PipelineAdapter, Streamlit form, Telegram+WhatsApp bots, QueueWorker | 0.00 (internal) |
| —   | 2026-06-05 | Crash-Recovery Checkpoint — scripts/checkpoint_state.py + Stop hook (ISS-022) | 0.00 (internal) |
| 031 | 2026-06-10 | RAG API — Railway → GCR migration (deploy_gcr.sh + rag-deploy-gcr.yml workflow) | 0.00 (internal) |

---

## Open Issues

| ID | Priority | Title | Status |
|----|----------|-------|--------|
| ISS-002 | P1 | Build `process/intent_registry.yaml` | DELIVERED |
| ISS-003 | P2 | Unified credential manager | OPEN |
| ISS-004 | P2 | Build `templates/` library (InvoiceTemplate, ChatbotTemplate) | OPEN |
| ISS-005 | P2 | Tiered thresholds in learning_loop.py | OPEN |
| ISS-006 | P2 | Source citation for advisory outputs | OPEN |
| ISS-007 | P3 | Provider-agnostic chatbot template | OPEN |
| ISS-008 | P2 | RAG retrieval system | DELIVERED |
| ISS-009 | P3 | Schedule GitHub Research runs (cron + digest commit) | OPEN |
| ISS-010 | P2 | Add `hosting_target` required field per intenti `*_deploy_*` | OPEN |
| ISS-011 | P1 | Acquire dispenser credentials before go-live (Stripe, Twilio, Telegram, VAT) | OPEN |
| ISS-012 | P2 | Implement `LLMClassifier` per richieste dispenser free-text | OPEN |
| ISS-013 | P3 | Implement `SatispayProvider` + `PayPalProvider` | OPEN |
| ISS-018 | P1 | Pablo: `gateway/pipeline_adapter.py` + FastAPI `/submit` + HMAC middleware | DELIVERED |
| ISS-019 | P1 | Sofia: `gateway/streamlit_app.py` wired to PipelineAdapter | DELIVERED |
| ISS-020 | P1 | Carlos: `gateway/bot_telegram.py` + `bot_whatsapp.py` wired to PipelineAdapter | DELIVERED |
| ISS-021 | P2 | Deploy Input Gateway: tutti e 3 i canali live | OPEN |
| ISS-022 | P1 | Crash-recovery flush: checkpoint periodico su project_state.md | DELIVERED |
| ISS-023 | P2 | Scope `etsy_digital_product_pack` intent | OPEN |
| ISS-024 | P2 | Scope `digital_product_listing_pack` intent | OPEN |
| ISS-025 | P1 | Valutare Lemon Squeezy vs Payhip come merchant-of-record (EU VAT) | OPEN |
| ISS-026 | P3 | HF Spaces paid deployment lane per chatbot/agent/techa deliverable | OPEN |
| ISS-027 | P3 | Gumroad secondary-channel publisher per PDF, planner, flashcard, journal | OPEN |
