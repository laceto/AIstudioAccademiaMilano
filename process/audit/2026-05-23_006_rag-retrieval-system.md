# Audit Log — Request 006

**Date:** 2026-05-23  
**Request ID:** 006  
**Submitted by:** Luigi

---

## User Input

> "Create embeddings with all the ai startup all the code must be indexed and embedded. Agents staff as well. Create a retrieval system."

---

## Pipeline Execution

```yaml
request_id: "006"
date: "2026-05-23"
intent: knowledge_query
outcome: success
user_input: "Create embeddings with all the ai startup all the code must be indexed\
  \ and embedded. Agents staff as well. Create a retrieval system."

agents_invoked:
  - name: Stacy
    role: intake_and_routing
    action: "Classified intent as knowledge_query. Confirmed no unknown product type —
      RAG knowledge base is €29.90 in pricing table. Routed to Gianni."
    duration_sec: 4
    status: success

  - name: Gianni
    role: technical_scoping
    action: "Scoped: (1) file crawler over all .py/.md/.json/.yaml; (2) word-level\
      \ overlapping chunker; (3) sentence-transformers local embed (no API cost) OR\
      \ OpenAI text-embedding-3-small; (4) numpy cosine search; (5) Streamlit UI for\
      \ interactive querying. Risk: index staleness if repo grows. Mitigation: staleness\
      \ check hook."
    duration_sec: 12
    status: success

  - name: Chiara
    role: implementation
    action: "Built scripts/embed_index.py (crawler + chunker + embed), scripts/retrieve.py\
      \ (load_index + cosine_similarity + retrieve + CLI), scripts/rag_chat.py (retrieve\
      \ + GPT synthesis), deliverables/rag/streamlit_rag_app.py (interactive UI with\
      \ sidebar controls). Wrote 22 tests in tests/test_retrieval.py."
    duration_sec: 95
    status: success

  - name: Stacy
    role: qa_review
    action: "Verified: embed_index.py includes all INCLUDE_GLOBS; retrieve.py raises\
      \ FileNotFoundError when index missing; cosine similarity handles zero vectors;\
      \ top-K limits respected; Streamlit app checks for missing index gracefully."
    duration_sec: 8
    status: success

  - name: Marco
    role: financial_controller
    action: "Priced at €29.90 (rag_knowledge_base). Actuarial note: E[value] = ongoing\
      \ productivity gain from instant codebase search > one-time cost. Risk reserve:\
      \ nil — local embedding has zero ongoing API cost."
    duration_sec: 3
    status: success

  - name: Francesca
    role: delivery
    action: "Pushed to claude/digital-communities-guide-a5lBV. Delivery: run\
      \ `python -m scripts.embed_index` once to build index, then `python -m scripts.retrieve\
      \ \"query\"` or deploy deliverables/rag/streamlit_rag_app.py to Streamlit Cloud."
    duration_sec: 5
    status: success

skills_used:
  - file_crawler
  - vector_embeddings
  - semantic_retrieval
  - rag_qa
  - streamlit_app_generation
  - openai_api_integration

learning_flags:
  new_skills:
    - vector_embeddings
    - semantic_retrieval
    - rag_qa
    - file_crawler
  new_mcp:
    - openai_embeddings
  risk_score: 2
  notes:
    - "New skill tier: semantic_retrieval is read-only (score=1), rag_qa needs OpenAI\
      \ key (score=2)"
    - "Added ISS-008 to global_settings.json, marked DELIVERED"
    - "New hook: embed_index_staleness_check fires before any semantic_retrieval call"
    - "Pricing: rag_knowledge_base = €29.90 added to pricing table"
```

---

## Deliverables

| File | Purpose |
|------|---------|
| `scripts/embed_index.py` | Crawl → chunk → embed → save `data/index/` |
| `scripts/retrieve.py` | Load index, cosine search, CLI |
| `scripts/rag_chat.py` | Retrieve + GPT synthesis CLI |
| `deliverables/rag/streamlit_rag_app.py` | Interactive Streamlit search UI |
| `tests/test_retrieval.py` | 22 tests covering chunking, collection, cosine similarity, round-trip, integration |
| `requirements-rag.txt` | `sentence-transformers`, `numpy`, `openai`, `faiss-cpu` |

---

## How to Use

```bash
# 1. Install dependencies
pip install -r requirements-rag.txt

# 2. Build the index (once, ~30s for local model)
python -m scripts.embed_index
# or with OpenAI embeddings:
python -m scripts.embed_index --provider openai

# 3. Query from CLI
python -m scripts.retrieve "how does the invoice template work?"
python -m scripts.retrieve "what agents review risk?" --top-k 8
python -m scripts.retrieve "learning loop threshold logic" --json

# 4. RAG chat (needs OPENAI_API_KEY)
python -m scripts.rag_chat "Explain the 6-agent pipeline"

# 5. Streamlit UI
streamlit run deliverables/rag/streamlit_rag_app.py
```

---

## What Gets Indexed

- `scripts/**/*.py` — all Python scripts including `learning_loop.py`, `embed_index.py`
- `templates/**/*.py` — invoice + chatbot templates
- `agents/**/*.md` — agent role definitions and actuarial specs
- `config/**/*.json` — global settings, pricing, skill registry
- `process/**/*.md` + `*.yaml` — pipeline docs, audit logs, intent registry
- `community/**/*.md` — all 5 digital community guides
- `deliverables/**/*.md` + `*.py` — all shipped outputs
- `tests/**/*.py` — the test suite itself

---

## Risk Assessment (Actuarial)

| Risk | P(event) | Impact | RU |
|------|----------|--------|----|
| Index staleness — new files not indexed | 0.30 | Medium (wrong answers) | 1.5 |
| OpenAI key missing for rag_chat | 0.20 | Low (CLI fallback works) | 0.4 |
| Large repo blows chunk count | 0.05 | Low (just slower) | 0.2 |

**Total RU: 2.1 — within auto-commit threshold (< 3). Committed automatically.**

---

*Delivered by AI Studio Accademia Milano — 2026-05-23*
