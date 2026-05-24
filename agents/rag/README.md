# RAG Team — AI Studio Accademia Milano

Four agents that provide semantic memory over the entire repo.
Built on **kitai + FAISS + BM25**. Modeled after `laceto/rss_feed`.

---

## Architecture

```
User query (or pipeline request)
    │
    ▼
[Context Injector]  ← UserPromptSubmit hook (always-on, real-time)
    │  reads CLAUDE_USER_PROMPT from env
    │  calls retrieve() — no LLM, sub-second
    │  prints <repo-context> block → injected into Claude's context
    │
    └─ for batch / deep queries:
         │
         ▼
       [Retriever]  hybrid BM25 + FAISS
            │  kitai.retriever: create_hybrid_retriever, reorder_docs
            │  kitai.query_translation: expand / decompose / step_back
            ▼
       [Synthesizer]  kitai.batch chat → RepoAnswer (Pydantic strict)
            │  async, 50% cheaper than sync, used by learning loop
            ▼
       {answer, confidence, key_files, gaps}

Index maintenance:
[Indexer]  → Stop hook or manual run
    collect_files() → chunk() → find_new(registry) →
    kitai.batch embed → FAISS init/update → save_registry()
    Incremental: content_hash per file, only changed chunks re-embedded
```

---

## Agents

### Indexer
**Script:** `scripts/rag/embed_repo.py`
**Role:** Walk the repo, chunk all files, embed via kitai batch API, store in FAISS.
**Trigger:** `Stop` hook or `python -m scripts.rag.embed_repo`
**Providers:**
- `--provider openai` (default) — kitai batch, 50% cheaper, async ~minutes
- `--provider local` — sentence-transformers, offline, no API key

**What it indexes:** `agents/`, `config/`, `process/`, `deliverables/`, `scripts/`,
`templates/`, `tests/`, `wiki/`, `CLAUDE.md`, `README.md`

**Invariants:**
- `data/rag_registry.tsv` — id, path, chunk_index, content_hash, guid
- `data/vectorstore/repo/` — FAISS `.faiss` + `.pkl`
- Registry saved AFTER vectorstore — write failure leaves registry consistent
- guid = `{rel_path}::{chunk_index}` — stable per-chunk identifier
- Dedup key: `(guid, content_hash)` — changed files get re-indexed

---

### Retriever
**Script:** `scripts/rag/retrieve_repo.py`
**Role:** Real-time hybrid BM25 + FAISS retrieval. Single entry point for all retrieval.
**kitai modules:** `kitai.retriever`, `kitai.query_translation`
**Public API:**
```python
retrieve(query, *, top_k=12, strategy="none") -> list[Document]  # no LLM call
ask(query, *, strategy="expand") -> dict  # {answer, sources, queries}
```
**Query strategies:**
- `expand` — paraphrase variants; best for synonym/phrasing coverage
- `decompose` — sub-questions; best for multi-part queries
- `step_back` — abstract questions; best for foundational context
- `none` — single query, no LLM translation; used by inject_context.py for speed

Resources cached at module level — FAISS + BM25 loaded once, all subsequent calls instant.

---

### Synthesizer
**Script:** `scripts/rag/synthesize.py`
**Role:** Async batch synthesis — submits (query, context) pairs via kitai.batch.
**Returns:** `RepoAnswer(answer, confidence, key_files, gaps)` — Pydantic strict schema
**Use cases:**
- Learning loop: "what did we learn from similar past requests?"
- Deep research: synthesize answers across multiple audit logs
- Bulk queries: 10 questions at once, 50% cheaper than synchronous

```bash
python -m scripts.rag.synthesize --queries "q1" "q2" "q3"  # submit
python -m scripts.rag.synthesize --poll                     # retrieve results
```

---

### Context Injector
**Script:** `scripts/rag/inject_context.py`
**Role:** Always-on hook — injects top-5 repo chunks before every Claude Code response.
**Trigger:** `UserPromptSubmit` hook in `.claude/settings.json`
**Behaviour:**
- Skips queries < 5 chars (single words, git commands)
- Skips silently if vectorstore not yet built
- Strategy `none` — fastest path, no LLM translation
- Prints `<repo-context>` block to stdout → Claude reads it as context
- Any error → exits 0 silently; never blocks the pipeline

---

## Quick Start

```bash
# 1. Install
pip install -r requirements-rag.txt

# 2. Build index (kitai batch — async, ~minutes)
python -m scripts.rag.embed_repo

# 3. Offline fallback (no API key needed)
python -m scripts.rag.embed_repo --provider local

# 4. Retrieve only (fast, no LLM)
python -m scripts.rag.retrieve_repo "how does invoice pricing work?" --no-llm

# 5. Full RAG answer
python -m scripts.rag.retrieve_repo "what agents handle email delivery?"

# 6. Batch synthesis
python -m scripts.rag.synthesize --queries "what skills does Chiara have?" "how does the learning loop work?"
python -m scripts.rag.synthesize --poll

# 7. Context injection is automatic via the UserPromptSubmit hook
```

---

## Registered Skills

| Skill | Agent | Intents |
|-------|-------|---------|
| `rag_indexer_kitai` | Indexer | `knowledge_query`, `repo_search` |
| `rag_retriever_hybrid` | Retriever | `knowledge_query`, `repo_search` |
| `rag_synthesizer_batch` | Synthesizer | `knowledge_query`, `deep_research` |
| `rag_context_injection` | Context Injector | always-on hook |
