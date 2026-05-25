---
name: doc-template-guide
type: howto
summary: How to write RAG-optimized internal docs for AI Studio Accademia Milano using internal_doc.md.
owner: Chiara
status: active
---

# Doc Template Guide

> How to write RAG-optimized internal docs using `internal_doc.md`.

---

## Overview

Every internal document — agent specs, skill docs, HOWTOs, pipeline descriptions — should
follow the `internal_doc.md` template. This ensures consistent structure and maximizes
retrieval quality under the studio's BM25+FAISS hybrid RAG system.

The RAG system chunks files at 400 words with a 50-word overlap. Sections written to
300–600 words land cleanly in one or two chunks. Sections shorter than 100 words may
merge with adjacent content; sections longer than 700 words split mid-paragraph and lose
coherence. Design around these boundaries.

The retriever blends 50% BM25 (keyword matching) and 50% FAISS (semantic similarity).
BM25 rewards exact terms: agent names, product keys (`rag_knowledge_base`), CLI flags,
JSON keys. FAISS rewards narrative prose and complete sentences. Write both: use exact
terms in prose, not just in code blocks.

---

## Required Frontmatter Fields

| Field | Type | Notes |
|-------|------|-------|
| `name` | string | Unique kebab-case slug. BM25 anchor — matches search queries. |
| `type` | enum | `agent \| skill \| howto \| pipeline \| reference` |
| `summary` | string | One sentence. Repeat as a blockquote below the title. |

Optional fields: `owner`, `status`, `related`, `citations`, `chunk_strategy`.

`chunk_strategy: header` is a reserved hint — the current chunker does not use it, but a
future semantic chunker will use it to split at section headers instead of word count.

---

## Section Size Guide

| Section | Target Words | Notes |
|---------|-------------|-------|
| Overview | 150–200 | Drive semantic retrieval here. Use exact terminology. |
| Architecture | 50–100 + diagram | Required for `type: agent` and `type: pipeline`. |
| Components | 200 + table | One sentence per row connecting table to prose. |
| Configuration | 100–150 | JSON block + prose. BM25 picks up JSON keys. |
| Quick Start | 80–120 | Commands + one sentence per command. |
| Triggers | table only | Required for hooked/automated components. |
| Notes | < 100 | Edge cases and gotchas only. |

---

## RAG Retrieval Tips

**For BM25 (keyword):**
- Use exact product type keys: `rag_knowledge_base`, `chatbot_app`, `static_landing_page`
- Use agent names verbatim: `Stacy`, `Gianni`, `Chiara`, `Marco`, `Francesca`
- Use intent names as used in audit logs: `calendar_integration`, `invoice_generation`
- Avoid abbreviations — write `retrieval-augmented generation` not `RAG` alone

**For FAISS (semantic):**
- Write complete sentences, not bullet fragments
- Describe relationships: "Chiara implements the spec Gianni produces" not "Chiara → impl"
- Include the *why*: "This agent blocks on unknown products because Marco cannot invoice
  without an approved price" encodes more meaning than "blocks on unknown products"

**Both retrievers benefit from:**
- Consistent section headers (copy them from the template, don't rename)
- Tables with meaningful column headers
- Repeating key terms in the `## Overview` section (it's always in the first chunk)

---

## Which `type` to Use

| Type | Use for |
|------|---------|
| `agent` | Named agents (Scout, Chiara, Marco, ContributorScout) |
| `skill` | Reusable implementation patterns registered in `global_settings.json` |
| `howto` | Step-by-step operational guides (credential setup, deploy procedures) |
| `pipeline` | End-to-end flows that connect multiple agents or systems |
| `reference` | Static reference data (pricing tables, topic lists, API schemas) |

---

## Quick Start

```bash
# Copy the template
cp templates/docs/internal_doc.md agents/my-agent/README.md

# Fill in required frontmatter (name, type, summary)
# Write the ## Overview section first — it drives retrieval

# After writing, re-embed to make it retrievable
python -m scripts.embed_index

# Verify it surfaces for expected queries
python -m scripts.retrieve "how does my-agent work?"
```

---

## Notes

The `templates/docs/example_agent.md` file shows a fully filled-in example using
ContributorScout. Use it as a reference before writing a new agent spec.

Backfilling existing `agents/**/*.md` files is tracked as **ISS-022** (P3).
