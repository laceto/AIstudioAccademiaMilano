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
model = SentenceTransformer("all-MiniLM-L6-v2")  # 384 dims
vectors = model.encode(["Stacy classifies user requests"], normalize_embeddings=True)
```

## Cosine Similarity

```
sim(A, B) = (A · B) / (|A| × |B|)    range: -1 to +1
```

This is what `scripts/retrieve.py` uses — vectorised over all chunks.

## Embedding Models at the Studio

| Model | Dims | Cost | Use when |
|-------|------|------|----------|
| `all-MiniLM-L6-v2` | 384 | Free | Default RAG |
| `text-embedding-3-small` | 1536 | $0.02/1M | Production |

*Next: [03 — Attention](03_attention.md)*
