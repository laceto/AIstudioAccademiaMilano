# 02 — Embeddings

> "An embedding is a learned lookup table. Token ID → dense vector."
> — Karpathy, *nanoGPT walkthrough*

---

## From Integer to Vector

After tokenization, each token ID passes through an **embedding matrix** `E` of shape `[vocab_size, d_model]`.

```
Vocab size:  50,257  (GPT-2)
d_model:        768  (GPT-2 small) / 12,288 (GPT-4)

Token ID 995 (" world")  →  E[995]  →  vector of 768 floats
```

This is just a table lookup — one row per token.  
The values are *learned* during training. Initially random.  
After training on billions of documents, nearby vectors = similar meaning.

---

## The Geometry of Meaning

```
king   - man + woman ≈ queen        (classic Word2Vec demo)
chat   + bot          ≈ chatbot
Paris  - France + Italy ≈ Rome      (geopolitical analogies)
```

This happens automatically from next-token prediction on large corpora.  
No one told the model that Paris is the capital of France.  
It inferred the relationship from co-occurrence statistics.

---

## Two Types of Embeddings at the Studio

### 1. Input Embeddings (inside the model)

Used internally by the LLM. Not directly accessible.  
`d_model` dimensions (768 to 12,288+).  
Change meaning as they pass through each transformer layer.

### 2. Sentence/Document Embeddings (what we use for RAG)

Produced by dedicated embedding models.  
Fixed after the forward pass — one vector per input chunk.  
Used for similarity search.

```python
# What our scripts/embed_index.py does:
from sentence_transformers import SentenceTransformer

model = SentenceTransformer("all-MiniLM-L6-v2")
# Output: 384-dimensional vectors

texts = [
    "Stacy is the intake agent who classifies user requests",
    "InvoiceTemplate renders PDF with fpdf2",
    "pricing: static_landing_page €9.90",
]
vectors = model.encode(texts, normalize_embeddings=True)
print(vectors.shape)  # (3, 384)
```

---

## Cosine Similarity — The Distance That Matters

Euclidean distance is broken in high-dimensional space (curse of dimensionality).  
Cosine similarity only cares about *direction*, not magnitude.

```
         vec_A · vec_B
sim =  ───────────────────
        |vec_A| × |vec_B|

Range: -1 (opposite) to +1 (identical)
```

```python
import numpy as np

def cosine_sim(a: np.ndarray, b: np.ndarray) -> float:
    return float(np.dot(a, b) / (np.linalg.norm(a) * np.linalg.norm(b)))

q = model.encode(["how much does a landing page cost?"])[0]
scores = [cosine_sim(q, v) for v in vectors]
print(scores)  # [0.21, 0.08, 0.74]  ← pricing chunk wins
```

This is exactly what `scripts/retrieve.py` does — vectorised over thousands of chunks.

---

## Positional Embeddings

Attention has no built-in sense of order. Token 1 and token 500 look the same.  
Solution: add a *position embedding* to each token embedding.

```
Input to transformer = token_embedding[t] + position_embedding[t]
```

Original Transformer (2017): sinusoidal fixed encoding.  
GPT-2: learned position embeddings (just another lookup table).  
GPT-4 / LLaMA: **Rotary Position Embedding (RoPE)** — encodes relative distances, extends to long contexts.

---

## Embedding Models at the Studio

| Model | Dims | Max tokens | Cost | Use when |
|-------|------|-----------|------|----------|
| `all-MiniLM-L6-v2` | 384 | 256 | Free (local) | Default RAG, fast |
| `all-mpnet-base-v2` | 768 | 384 | Free (local) | Higher quality |
| `text-embedding-3-small` | 1536 | 8191 | $0.02/1M | Production RAG |
| `text-embedding-3-large` | 3072 | 8191 | $0.13/1M | Best quality |

**Studio rule:** Build with local. Switch to `text-embedding-3-small` for production.

---

## Build It: Embedding Matrix From Scratch

```python
import torch
import torch.nn as nn

vocab_size = 50_257   # GPT-2
d_model    = 768

# Just a learnable table
emb = nn.Embedding(vocab_size, d_model)

tokens = torch.tensor([15496, 11, 995])  # "Hello, world"
vectors = emb(tokens)                    # shape: (3, 768)
print(vectors.shape)                     # torch.Size([3, 768])
```

During backpropagation, gradient flows through the table lookup — only the rows that were used get updated. Elegant.

---

*Next: [03 — Attention](03_attention.md) — how tokens talk to each other*
