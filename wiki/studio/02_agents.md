# Agent Roster

All agents active in the studio. Full specs in `agents/`.

---

## Delivery Pipeline (6 steps, always in order)

| Agent | Step | Role | Invoke when |
|-------|------|------|-------------|
| **Stacy** | 1 + 4 | Input classification + QA | Every request (auto) |
| **Gianni** | 2 | Technical scoping | Every request (auto) |
| **Chiara** | 3 | Implementation | Every request (auto) |
| **Marco** | 5 | Pricing + invoice | Every request (auto) |
| **Francesca** | 6 | Delivery + audit log | Every request (auto) |

**Luigi** — Founder, final authority. Overrides Marco on unknown products. Never skipped.

---

## Risk Agents (actuarial oversight)

All use formula: `P(event) × impact × blast_radius` → Risk Units (RU). Flag at 2σ.

| Agent | Focus | Triggers at |
|-------|-------|-------------|
| **Technical Auditor** | Code/deployment integrity | Every new build |
| **Financial Controller** | Project economics, margin | Before delivery |
| **Operational Monitor** | Pipeline uptime, automation health | On pipeline failures |
| **Reputation Guardian** | Output quality, public demos | Before client handoff |
| **Compliance Agent** | ToS, GDPR, API compliance | Every external API usage |

---

## Research Department

GitHub AI discovery pipeline. Run manually or on schedule (ISS-009).

| Agent | Role |
|-------|------|
| **Scout** | Search GitHub for trending AI repos |
| **Analyst** | Score repos on weighted actuarial model |
| **Curator** | Deduplicate + categorise shortlist |
| **Reporter** | Weekly digest + Streamlit dashboard update |

```bash
python scripts/github_research/main.py --topics llm rag ai-agents --min-stars 200
```

---

## RAG Team

Semantic memory over the entire repo. Always-on via `UserPromptSubmit` hook — top-5 chunks injected before every Claude Code response. See `agents/rag/README.md`.

| Agent | Role | Script |
|-------|------|--------|
| **RAG/Indexer** | Batch-embed all repo files via kitai → FAISS vectorstore | `scripts/rag/embed_repo.py` |
| **RAG/Retriever** | Hybrid BM25 + FAISS retrieval, query translation | `scripts/rag/retrieve_repo.py` |
| **RAG/Synthesizer** | Async batch synthesis via kitai.batch, Pydantic output | `scripts/rag/synthesize.py` |
| **RAG/ContextInjector** | UserPromptSubmit hook — prepends top-5 chunks every call | `scripts/rag/inject_context.py` |

```bash
python -m scripts.rag.embed_repo          # build index
python -m scripts.rag.retrieve_repo "query" --no-llm   # retrieval only
python -m scripts.rag.retrieve_repo "query"            # full RAG
```

---

## Input Gateway Team

Three parallel channels that feed requests into the 6-agent pipeline. See `agents/input_gateway/README.md` and ISS-018/019/020.

| Agent | Channel | Status |
|-------|---------|--------|
| **Pablo** | FastAPI `/submit` + HMAC middleware + `pipeline_adapter.py` | ISS-018 open |
| **Sofia** | Streamlit UI wired to PipelineAdapter | ISS-019 open |
| **Carlos** | Telegram bot + WhatsApp webhook → PipelineAdapter | ISS-020 open |

---

## V2 Team (delivery improvement)

Triggered when: Luigi asks, Stacy QA flags a shipped defect, Marco pricing adequacy < 0.85, or Reputation Guardian RU > 5.

| Agent | Focus |
|-------|-------|
| **Quality Reliability Lead** | SLOs, tests, accessibility, observability |
| **Core Architect** | Stack, coupling, reusables to extract |
| **API Product Designer** | Surface area, conversion, cross-product integration |
| **Devil's Advocate** | Hidden costs, unverified assumptions, price-tier veto |

---

## Specialist Agents

Run outside the pipeline. Invoked directly by Luigi or Stacy.

| Agent | Role | Authority |
|-------|------|-----------|
| **IT Staff** | Domains, DNS, email, credentials, accounts registry | Advisory — Luigi approves all writes |
| **Valentina** | Platform profiles, bios, multi-platform publishing | Luigi approves before any publish |
| **Lorenzo** | Task management, open issues, blockers | Owns task list |
| **Wiki Curator** | Maintains `wiki/` — updates on new models, techniques, or studio changes | Invoked by Luigi or trigger events |
