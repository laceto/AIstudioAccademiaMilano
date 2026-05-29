# AI Studio Accademia Milano

A one-human AI enterprise that turns any user request into a tangible, deployed output — website, PDF, invoice, chatbot, calendar sync — in under 2 minutes, paid at a physical dispenser.

**Founder:** Luigi Aceto

---

## How It Works

Every request flows through a 6-agent pipeline:

```
User Input (text, voice, or QR at dispenser)
  |
  v
Stacy        Intent classification + pricing check
  |
  v
Gianni       Technical scoping + stack selection
  |
  v
Chiara       Implementation (code, PDF, content)
  |
  v
Stacy QA     Output validation + security check
  |
  v
Marco        Payment + invoice (actuarial pricing)
  |
  v
Francesca    Delivery: deploy, email, or print receipt
```

A parallel layer of 5 **Risk Agents** (Technical Auditor, Financial Controller, Operational Monitor, Reputation Guardian, Compliance Agent) monitors every step with actuarial scoring: `P(event) × impact × blast_radius → Risk Units`.

The pipeline can be triggered three ways:
- **Physical dispenser** — QR code → Streamlit form → Stripe → pipeline
- **GitHub Actions** — `workflow_dispatch` or open a GitHub issue
- **CLI** — `python scripts/run_pipeline_cli.py "Build a chatbot"`

---

## Delivered Products

| # | Product | Price | Deliverable |
|---|---------|-------|-------------|
| 001 | Bakery website (HTML + Tailwind) | €9.90 | `deliverables/2026-05-23_001_bakery-website/` |
| 002 | PDF creation + Gmail delivery | €2.40 | `deliverables/2026-05-23_002_pdf-email/` |
| 003 | Invoice PDF + Gmail delivery | €3.90 | `deliverables/2026-05-23_003_invoice-pdf-email/` |
| 004 | Strategic report: AI startup monetisation | €4.90 | `deliverables/2026-05-23_004_ai_startup_street_monetization.md` |
| 005 | Streamlit chatbot + OpenAI streaming | €19.90 | `deliverables/2026-05-23_005_chatbot/` |
| 006 | RAG system: semantic search over all code | €29.90 | `deliverables/rag/` |
| 007 | WhatsApp/Telegram → Calendar sync (Google, Outlook, Apple) | €14.90 | `deliverables/2026-05-23_007_calendar-sync/` |
| 008 | Algo Trading Bot — Alpaca paper, SMA(20/50)+RSI, Streamlit/Plotly | €24.90 | `deliverables/2026-05-23_008_algo-trading/` |
| 009 | LinkedIn post generator from GitHub activity (Claude voice) | €4.90 | `deliverables/2026-05-23_009_linkedin-post-generator/` |
| 010 | Valentina agent — profile setup & multi-platform publishing pipeline | €14.90 | `deliverables/2026-05-23_010_profile-setup/` |
| 011 | Milan Weather Dashboard (Streamlit + OpenWeatherMap) | €9.90 | `deliverables/2026-05-24_011_bakery-v2/` |
| 012 | Discord Bot — AI chat + 4 slash commands + announcer webhook (Claude + OpenWeatherMap) | €19.90 | `deliverables/2026-05-24_012_discord-bot/` |
| 013 | techa Streamlit deploy (LangGraph trading agents + TA-Lib, HF Spaces / Cloud Run) | €19.90 | `deliverables/2026-05-24_013_techa-deploy/` |
| 014 | Dispenser input v1 — QR/Streamlit form, Stripe, WhatsApp+Telegram delivery | €0.00 (internal) | `deliverables/2026-05-24_014_dispenser/` |
| 015 | Logo Generator — circle/square/minimal styles, configurable size + accent | €0.00 (internal) | `deliverables/2026-05-25_015_logo-generator/` |
| 016 | AI Studio LangGraph assistant — multi-agent graph, parallel department nodes | €0.00 (internal) | `deliverables/2026-05-25_016_aistudio-langgraph/` |
| 017 | Lawyer LangGraph + Mindful Bot — white-label legal assistant + psychology entry | €0.00 (internal) | `deliverables/2026-05-25_017_lawyer-mindful/` |
| 018 | SOAP Note Generator — psychology vertical Streamlit app (Diletta pilot) | €0.00 (internal) | `deliverables/2026-05-25_018_soap-note/` |
| 019 | Studio Digital Twin — LangGraph parallel simulation of the 6-agent pipeline | €0.00 (internal) | `deliverables/2026-05-25_019_digital-twin/` |
| 020 | Mind Dashboard — daily AI briefing from raw journal text | €9.90 | `deliverables/2026-05-26_020_mind-dashboard/` |
| 021 | Micro-Syllabus & Flashcard Generator — 7-day plan + 10 Anki cards (gpt-4o) | €14.90 | `deliverables/2026-05-26_021_micro-syllabus/` |
| 022 | Family Archivist — voice/text → story archive, local + Claude/OpenAI modes | €14.90 | `deliverables/2026-05-26_022_family-archivist/` |
| 023 | Mediterranean Meal Planner — 7-day batch-cook matrix + grocery list (gpt-4o) | €14.90 | `deliverables/2026-05-26_023_meal-planner/` |
| 024 | The Niccolò Chronicles — WhatsApp time-capsule → monthly Markdown chronicle | €14.90 | `deliverables/2026-05-26_024_niccolo-chronicles/` |
| 025 | Chat-to-Insights RSS Pipeline — parses Claude sessions/WhatsApp/audit logs as RSS; keyword, timeline, heatmap, sentiment; RSS 2.0 + OPML export | €0.00 (internal) | `deliverables/2026-05-27_025_chat-analysis/` |
| 026 | Trading Agent Team Dashboard + API — 4 agents (US Alpaca + Italian yfinance), FastAPI (9 endpoints), Streamlit, techa integration | €24.90 | `deliverables/2026-05-27_026_trading-agent-dashboard/` |
| 027 | DIY Electrical Brainstorm — affinity groups + API landscape for home electrical assistant | €4.90 | `deliverables/2026-05-27_027_diy-electrical-brainstorm/` |
| 028 | Team Showcase — Streamlit app: 6-agent pipeline, 5 risk agents, 4 department teams, open issues | €0.00 (internal) | `deliverables/2026-05-27_028_team-showcase/` |
| — | GitHub AI Research Department (Scout/Analyst/Curator/Reporter) | €0.00 (internal) | `deliverables/github-research/` |

---

## Key Systems

### Semantic Search (RAG)
All repo files are indexed and searchable:
```bash
pip install -r requirements-rag.txt
python -m scripts.embed_index
python -m scripts.retrieve "how does Marco price unknown products?"
streamlit run deliverables/rag/streamlit_rag_app.py
```

### GitHub AI Research Department
Four agents (Scout, Analyst, Curator, Reporter) that continuously scan GitHub for emerging AI tools and produce ranked reports:
```bash
pip install -r requirements-research.txt
export GITHUB_TOKEN=ghp_...    # optional — raises rate limit 60 -> 5000 req/h
python scripts/github_research/main.py --topics llm rag ai-agents --min-stars 200
streamlit run deliverables/github-research/streamlit_research_app.py
```
See `agents/research/README.md` for the full department spec.

### Chat-to-Insights RSS Pipeline (D025)
Treats Claude Code sessions, WhatsApp exports, and audit logs as RSS feeds:
```bash
streamlit run deliverables/2026-05-27_025_chat-analysis/app.py
```
Upload any WhatsApp `.txt` export, or enable "Audit logs" to analyse the full delivery history.
Exports valid RSS 2.0 + OPML importable into Feedly, NewsBlur, etc.

### Trading Agent Team Dashboard + API (D026)
Four named agents (Alpha/Beta/Gamma via Alpaca paper; Delta via yfinance Italian blue-chips), shared JSON store, Streamlit dashboard, FastAPI REST API (9 endpoints):
```bash
streamlit run deliverables/2026-05-27_026_trading-agent-dashboard/app.py
uvicorn deliverables.2026-05-27_026_trading-agent-dashboard.api:app --reload
```
Integrates with techa (D013) for pattern enrichment. `paper=True` is hardcoded.

### Team Showcase (D028)
Live visualisation of the entire AI Studio team: agents, risk layer, department teams, open issues:
```bash
streamlit run deliverables/2026-05-27_028_team-showcase/app.py
```

### Digital Presence Pipeline
Bridges D009 (LinkedIn post generator) with D010 (Valentina publisher). One command generates from GitHub activity and auto-posts to Telegram, Twitter/X, Discord. Fires every Monday 09:00 UTC via GitHub Actions:
```bash
python scripts/digital_presence_pipeline.py --days 7 --platforms telegram
python scripts/digital_presence_pipeline.py --dry-run   # generate only
```
Generated posts saved to `process/digital-presence/`.

### RAG Agent Team
Four agents providing semantic memory over the entire repo (kitai + FAISS + BM25):
```bash
pip install -r requirements-rag.txt
python -m scripts.rag.embed_repo                                         # build index
python -m scripts.rag.retrieve_repo "how does invoice pricing work?" --no-llm
python -m scripts.rag.retrieve_repo "explain the 6-agent pipeline"       # full RAG
python -m scripts.rag.synthesize --queries "what skills does Chiara use?" # async batch
```
Context injection is always-on via `UserPromptSubmit` hook — top-5 repo chunks are injected before every Claude Code response.
See `agents/rag/README.md` for the full architecture.

### Suit Manager (White-Label)
The pipeline ships as a reusable "suit" — each white-label instance gets its own `config/suits/SXXX.yaml`:
```bash
python scripts/suit_manager.py list
python scripts/suit_manager.py show S001
python scripts/suit_manager.py create S002 --name "Acme AI Studio" --owner "Jane Doe" --email "jane@acme.com"
```
S001 = AI Studio Accademia Milano (origin). All suit configs inherit from `suit_schema.yaml`.

### Aziende Fabrizia (Medical Vertical)
`aziende-fabrizia/diabetologia-endocrinologia/` — Fabrizia Aceto's digital medical practice:
- **PubMed Researcher** — AI-powered literature search and summarisation
- **Avatar Digitale** — personalised digital twin for patient-facing interactions
- **Research Radar** — multi-source aggregator (OpenAlex, Semantic Scholar, Europe PMC, CrossRef, ClinicalTrials)
- **Meta-Analysis** — automated statistical meta-analysis from uploaded studies

### GitHub Actions Pipeline
The full 6-agent pipeline runs headlessly on GitHub Actions:
- **Manual trigger** — `Actions → AI Studio Pipeline → Run workflow`
- **Issue-driven** — open a GitHub issue; pipeline runs on `issues.opened` and posts the result as a comment
```yaml
inputs:
  request: "Create a Streamlit chatbot with OpenAI streaming"
  user_name: "Luigi"
  provider: openai | anthropic
```

### LLM Education Wiki
Karpathy-style, 8 chapters + runnable code:
```
wiki/llm/01_tokenization.md  through  08_reasoning_models.md
wiki/llm/code/  —  bpe_minimal.py, nano_attention.py, sampling_demo.py
```

---

## Repository Structure

```
agents/          Staff, risk, research, RAG team, and Valentina agent specs
aziende-fabrizia/  Fabrizia's digital companies vertical (diabetologia-endocrinologia)
config/          global_settings.json + accounts_registry.yaml + suits/
credentials/     registry.md — step-by-step guide for all credentials
data/            vectorstore/repo/ (FAISS index) + synthesis_results/
deliverables/    One folder per completed request (YYYY-MM-DD_NNN_slug/)
gateway/         Input Gateway: FastAPI /submit + Streamlit UI + Telegram/WhatsApp bots
logs/            learning_loop.log (gitignored)
process/         Pipeline spec, audit logs, intent_registry.yaml, digital-presence posts
scripts/         Core scripts: learning_loop, suit_manager, run_pipeline_cli, log_analytics
scripts/rag/     embed_repo, retrieve_repo, synthesize, inject_context
scripts/chat_analysis/   Chat-to-RSS pipeline: parsers, analyzer, RSS/OPML builder
scripts/github_research/  Scout → Analyst → Curator → Reporter pipeline
templates/       Reusable factories: pdf/ (InvoiceTemplate), streamlit/ (ChatbotTemplate), web/
tests/           TDD test suites (pytest)
wiki/llm/        Karpathy-style LLM education wiki (8 chapters + code)
.github/workflows/  pipeline.yml (6-agent CI) + rag-bootstrap.yml (index rebuild)
```

---

## Pricing

| Product | Price |
|---------|-------|
| Static landing page | €9.90 |
| Premium landing page | €29.90 |
| Commercial landing page | €45.90 |
| PDF document | €1.90 |
| Invoice PDF | €3.90 |
| Strategic report | €4.90 |
| Chatbot app | €19.90 |
| Email delivery | €0.50 |
| RAG knowledge base | €29.90 |
| Calendar integration | €14.90 |
| Weather dashboard | €9.90 |
| Agent deploy (Streamlit) | €19.90 |
| Algo trading | €24.90 |
| Mind dashboard / journal | €9.90 |
| Micro-syllabus & flashcards | €14.90 |
| Family archivist | €14.90 |
| Mediterranean meal planner | €14.90 |
| Niccolò Chronicles | €14.90 |
| Unknown product | **blocked — Luigi approves** |

---

## Docs

- `CLAUDE.md` — operational guide for Claude Code (pipeline, security, learning loop, audit format)
- `agents/README.md` — full agent profiles + actuarial risk agent specs
- `agents/research/README.md` — GitHub Research Department
- `agents/rag/README.md` — RAG Team architecture
- `agents/input_gateway/README.md` — Input Gateway Team (Pablo, Sofia, Carlos)
- `config/suits/suit_schema.yaml` — white-label suit schema
- `process/User_Request_to_Delivery.md` — end-to-end pipeline spec
- `process/learning_loop.md` — how the system learns from every request
- `aziende-fabrizia/README.md` — Fabrizia's digital companies vertical
