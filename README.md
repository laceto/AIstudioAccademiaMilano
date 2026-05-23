# AI Studio Accademia Milano

A one-human AI enterprise that turns any user request into a tangible, deployed output — website, PDF, invoice, chatbot, calendar sync, trading bot, LinkedIn post — in under 2 minutes, paid at a physical dispenser.

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

Running in parallel:
- **5 Risk Agents** (Technical Auditor, Financial Controller, Operational Monitor, Reputation Guardian, Compliance Agent) — actuarial monitoring on every step
- **Valentina** (Profile Setup & Publishing) — announces new deliverables across all platforms
- **4 Research Agents** (Scout, Analyst, Curator, Reporter) — daily/weekly GitHub AI discovery

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
| 008 | Algo trading bot (SMA crossover, Alpaca paper) | €24.90 | `deliverables/2026-05-23_008_algo-trading/` |
| 009 | LinkedIn post generator from GitHub activity | €4.90 | `deliverables/2026-05-23_009_linkedin-post-generator/` |
| 010 | Profile setup & publishing automation (Valentina) | €14.90 | `deliverables/2026-05-23_010_profile-setup/` |

---

## Key Systems

### Semantic Search (RAG)
```bash
pip install -r requirements-rag.txt
python -m scripts.embed_index
python -m scripts.retrieve "how does Marco price unknown products?"
streamlit run deliverables/rag/streamlit_rag_app.py
```

### GitHub AI Research Department
Four agents (Scout, Analyst, Curator, Reporter) scan GitHub for emerging AI tools and produce ranked weekly digests:
```bash
pip install -r requirements-research.txt
export GITHUB_TOKEN=ghp_...    # optional — raises rate limit 60 → 5000 req/h
python scripts/github_research/main.py --topics llm rag ai-agents --min-stars 200
streamlit run deliverables/github-research/streamlit_research_app.py
```
Scheduled automatically via GitHub Actions (daily S-tier alert + weekly digest). See `agents/research/README.md`.

### LinkedIn Post Generator
Reads recent commits/releases from any public GitHub repo and generates a post in Luigi's voice:
```bash
export ANTHROPIC_API_KEY=sk-ant-...
export GITHUB_TOKEN=ghp_...    # optional
pip install -r deliverables/2026-05-23_009_linkedin-post-generator/requirements.txt
python deliverables/2026-05-23_009_linkedin-post-generator/main.py --repo laceto/hello-world --copy
```

### Profile Setup & Publishing (Valentina)
Generates bios and first posts for 9 platforms; publishes to Twitter/X, Telegram, Discord, Reddit:
```bash
export ANTHROPIC_API_KEY=sk-ant-...
cd deliverables/2026-05-23_010_profile-setup
python main.py --generate          # generates all bios + first posts → output/
python main.py --publish telegram  # confirm + send
python main.py --list              # see all platforms + publish method
```
See `process/profile_setup_checklist.md` for per-platform signup URLs and status tracker.

### Algo Trading Bot
SMA crossover strategy on Alpaca paper trading account:
```bash
export ALPACA_API_KEY=your_key
export ALPACA_SECRET_KEY=your_secret
pip install -r deliverables/2026-05-23_008_algo-trading/requirements.txt
python deliverables/2026-05-23_008_algo-trading/main.py          # dry run
python deliverables/2026-05-23_008_algo-trading/main.py --live   # execute paper orders
streamlit run deliverables/2026-05-23_008_algo-trading/dashboard.py
```

### LLM Education Wiki
Karpathy-style, 7 chapters + runnable code:
```
wiki/llm/01_tokenization.md  through  07_studio_playbook.md
wiki/llm/code/  —  bpe_minimal.py, nano_attention.py, sampling_demo.py
```

---

## Repository Structure

```
agents/          Agent roles: pipeline (Stacy/Gianni/Chiara/Marco/Francesca)
                              + Valentina (publishing)
                              + risk team (5 agents)
                              + research department (4 agents)
config/          global_settings.json — skills, pricing, hooks, MCP
community/       Community strategy, platform matrix, digital presence docs
deliverables/    One folder per completed request (001–010)
framework/       Architecture decisions, mission, capital model, risk architecture
process/         Pipeline spec, intent registry, audit logs, learning loop,
                 risk review process, 90-day roadmap, profile setup checklist
projects/        Git submodule registry for future standalone repos
scripts/         learning_loop.py, credential_manager.py, embed_index.py,
                 retrieve.py, github_research/
templates/       Reusable PDF and Streamlit templates
tests/           TDD test suites (pytest)
wiki/llm/        Karpathy-style LLM education wiki (7 chapters + code)
```

---

## Pricing

| Product | Price |
|---------|-------|
| Static landing page | €9.90 |
| PDF document | €1.90 |
| Invoice PDF | €3.90 |
| Strategic report | €4.90 |
| LinkedIn post (per run) | €4.90 |
| Email delivery | €0.50 |
| Chatbot app | €19.90 |
| Algo trading bot | €24.90 |
| Calendar integration | €14.90 |
| Profile setup automation | €14.90 |
| RAG knowledge base | €29.90 |
| Unknown product | **blocked — Luigi approves** |

---

## Project Registry

All deliverables and internal systems are tracked in [`ProjectRegistry.md`](ProjectRegistry.md).
New standalone projects follow the submodule convention in [`projects/README.md`](projects/README.md) and [`project-setup-rules.md`](project-setup-rules.md).

---

## Docs

- `CLAUDE.md` — operational guide for Claude Code (pipeline, security, learning loop, audit format)
- `agents/README.md` — full agent profiles (pipeline + Valentina + risk + research)
- `agents/risk/README.md` — AI Risk Management Department (5 agents)
- `agents/research/README.md` — GitHub Research Department (4 agents)
- `ProjectRegistry.md` — central registry of all deliverables and systems
- `process/profile_setup_checklist.md` — per-platform signup + status tracker
- `process/User_Request_to_Delivery.md` — end-to-end pipeline spec
- `process/execution_roadmap_90_days.md` — community launch roadmap
- `framework/ai_risk_management_team.md` — risk architecture
