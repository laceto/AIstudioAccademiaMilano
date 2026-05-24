# 02 — Embeddings

> "An embedding is a learned lookup table. Token ID → dense vector."

## Token ID → Vector

```
Vocab: 50,257 tokens  |  d_model: 768 (GPT-2) to 12,288 (GPT-4)
Token 995 (" world") → E[995] → vector of 768 floats
```

Values learned during training. After pretraining on billions of docs: nearby vectors = similar meaning.

```
king - man + woman ≈ queen
Paris - France + Italy ≈ Rome
```

## Two Types at the Studio

**Input embeddings** — internal to the LLM, 768-12288 dims, change per layer.  
**Sentence embeddings** — dedicated models, one vector per chunk, used for RAG.

```python
from sentence_transformers import SentenceTransformer
model = SentenceTransformer("all-MiniLM-L6-v2")  # 384 dims, free
vectors = model.encode(["Stacy classifies user requests"], normalize_embeddings=True)
```

## Cosine Similarity

```
sim(A, B) = (A · B) / (|A| × |B|)    range: -1 to +1
```

This is what `scripts/retrieve.py` uses — vectorised over all chunks.

## Embedding Models (2025 comparison)

| Model | Dims | Cost | Use when |
|-------|------|------|----------|
| `all-MiniLM-L6-v2` | 384 | Free, local | Default RAG, dev |
| `nomic-embed-text` | 768 | Free, local (via HF) | Better quality, still free |
| `text-embedding-3-small` | 1536 | $0.02/1M tokens | Production RAG |
| `text-embedding-3-large` | 3072 | $0.13/1M tokens | High-precision retrieval |
| `BAAI/bge-large-en-v1.5` | 1024 | Free via HF | SOTA open-source |

```python
# Free, high-quality via HuggingFace
from sentence_transformers import SentenceTransformer
model = SentenceTransformer("nomic-ai/nomic-embed-text-v1", trust_remote_code=True)
vecs = model.encode(["search_document: " + chunk for chunk in chunks])
```

`nomic-embed-text` requires the `search_document:` prefix for asymmetric retrieval (queries use `search_query:`).

## Vector Stores

| Store | Type | When to use |
|-------|------|-------------|
| In-memory numpy | No DB | < 10K chunks, scripts |
| ChromaDB | Local file | Single-user, dev |
| FAISS | Local file | Large-scale, no infra |
| Pinecone / Weaviate | Cloud | Multi-user, production |

```python
import chromadb
client = chromadb.PersistentClient(path="data/vectorstore/repo")
col = client.get_or_create_collection("repo_chunks")
col.add(documents=chunks, embeddings=vecs.tolist(), ids=[str(i) for i in range(len(chunks))])

# Query
results = col.query(query_embeddings=[query_vec.tolist()], n_results=5)
```

The studio uses FAISS in `scripts/embed_index.py` and `scripts/retrieve.py`.

*Next: [03 — Attention](03_attention.md)*
