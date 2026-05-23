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

A parallel layer of 5 **Risk Agents** (Technical Auditor, Financial Controller, Operational Monitor, Reputation Guardian, Compliance Agent) monitors every step with actuarial scoring.

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

### LLM Education Wiki
Karpathy-style, 7 chapters + runnable code:
```
wiki/llm/01_tokenization.md  through  07_studio_playbook.md
wiki/llm/code/  —  bpe_minimal.py, nano_attention.py, sampling_demo.py
```

---

## Repository Structure

```
agents/          Agent role definitions (staff + risk + research department)
config/          global_settings.json — single source of truth for skills, pricing, hooks
deliverables/    One folder per completed request
process/         Pipeline spec, audit logs, learning loop, risk review process
scripts/         learning_loop.py, embed_index.py, retrieve.py, github_research/
templates/       Reusable PDF and Streamlit templates
tests/           TDD test suites (pytest)
wiki/llm/        Karpathy-style LLM education wiki
```

---

## Pricing

| Product | Price |
|---------|-------|
| Static landing page | €9.90 |
| PDF document | €1.90 |
| Invoice PDF | €3.90 |
| Strategic report | €4.90 |
| Chatbot app | €19.90 |
| Email delivery | €0.50 |
| RAG knowledge base | €29.90 |
| Calendar integration | €14.90 |
| Unknown product | **blocked — Luigi approves** |

---

## Docs

- `CLAUDE.md` — operational guide for Claude Code (pipeline, security, learning loop, audit format)
- `agents/README.md` — full agent profiles + actuarial risk agent specs
- `agents/research/README.md` — GitHub Research Department
- `process/User_Request_to_Delivery.md` — end-to-end pipeline spec
- `process/learning_loop.md` — how the system learns from every request
