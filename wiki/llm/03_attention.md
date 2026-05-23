# 03 — Attention

> "Attention is all you need. And attention is just a weighted average."
> — Karpathy, *Let's build GPT from scratch* (YouTube, 2023)

---

## The Problem Attention Solves

Consider: `"The animal didn't cross the street because it was too tired."`

What does `"it"` refer to? **The animal.**  
Not the street. Not the crossing. The *animal*.

To answer this, token `"it"` needs to *look back* at earlier tokens and decide which ones matter.  
That's exactly what attention does.

---

## Self-Attention in 20 Lines

```python
import torch
import torch.nn.functional as F

def self_attention(x, W_q, W_k, W_v):
    """
    x:    (T, d_model)  — sequence of T token embeddings
    W_q, W_k, W_v: (d_model, d_head)  — learned weight matrices
    returns: (T, d_head)  — attended output
    """
    T, d = x.shape
    d_head = W_q.shape[1]

    Q = x @ W_q   # (T, d_head)  "What am I looking for?"
    K = x @ W_k   # (T, d_head)  "What do I contain?"
    V = x @ W_v   # (T, d_head)  "What will I send if chosen?"

    # Scaled dot-product attention
    scale = d_head ** 0.5
    scores = (Q @ K.T) / scale   # (T, T)  — every token vs every token

    # Causal mask: token i cannot see token j > i (autoregressive)
    mask = torch.triu(torch.ones(T, T), diagonal=1).bool()
    scores = scores.masked_fill(mask, float("-inf"))

    weights = F.softmax(scores, dim=-1)  # (T, T)  — sum to 1 per row

    return weights @ V   # (T, d_head)  — weighted average of values
```

---

## Q, K, V — The Library Metaphor

| Component | Role | Metaphor |
|-----------|------|----------|
| **Query (Q)** | What this token is looking for | Search query |
| **Key (K)** | What each token advertises about itself | Book index |
| **Value (V)** | The actual content to retrieve | Book content |

```
Token "it" sends query Q_it into the room.
Every token computes its relevance: sim(Q_it, K_token).
"animal" scores highest → gets highest weight in softmax.
Output = weighted average of all V → mostly V_animal flows into "it"'s representation.
```

---

## The Attention Matrix

```
Input:  ["The", "animal", "didn't", "cross", "it"]

Attention weights for token "it" (last row):

          The   animal  didn't  cross   it
  it:  [ 0.05,  0.72,   0.08,   0.09, 0.06 ]
                  ^^^^  ← "it" attends most to "animal"
```

This matrix is never explicitly stored — it's recomputed on every forward pass.

---

## Multi-Head Attention

One attention head can only look for one type of relationship at a time.  
Run `h` heads in parallel, each with independent W_q, W_k, W_v.

```
Head 1 might track: syntactic subject-verb agreement
Head 2 might track: coreference ("it" → "animal")
Head 3 might track: local context (adjacent tokens)
...
Head 12 might track: semantic topics
```

```python
# PyTorch built-in
import torch.nn as nn

mha = nn.MultiheadAttention(
    embed_dim=768,   # d_model
    num_heads=12,    # h = 12 for GPT-2 small
    batch_first=True,
)

x = torch.randn(1, 10, 768)   # (batch, seq_len, d_model)
out, weights = mha(x, x, x)   # Q=K=V=x for self-attention
print(out.shape)               # (1, 10, 768)
```

All heads are concatenated then projected back to `d_model`. O(h × d_head) = O(d_model).

---

## Why Scaled Dot-Product?

Without the `/ sqrt(d_head)` scaling:
- Dot products grow large as `d_head` increases
- Softmax saturates → one token gets weight ≈ 1, others ≈ 0
- Gradients vanish → training stalls

Scale by `sqrt(d_head)` keeps variance ≈ 1. Simple fix, huge impact.

---

## Attention Complexity

The quadratic cost everyone talks about:

```
Computing Q @ K.T is O(T²)   where T = sequence length

GPT-4 with 128K context: T = 131,072
131,072² = 17 billion operations per attention layer
GPT-4 has ~120 layers
```

This is why long contexts cost so much. Research directions:
- **Flash Attention** (Dao et al.) — same math, faster IO, standard now
- **Sliding window** (Mistral) — each token only attends to nearby tokens
- **Linear attention** — approximate, O(T) but lower quality

---

## Studio Takeaways

- Keep system prompts short — every token in context is paid for in compute
- RAG retrieves only the 5 most relevant chunks instead of dumping the full codebase into context
- For our 128K-context calls (strategic reports), price accordingly

---

*Next: [04 — Transformer Architecture](04_transformer.md) — putting it all together*
