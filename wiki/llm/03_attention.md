# 03 — Attention

> "Attention is all you need. And attention is just a weighted average."
> — Karpathy

## Self-Attention in 20 Lines

```python
import torch, torch.nn.functional as F

def self_attention(x, W_q, W_k, W_v):
    # x: (T, d_model)   W_*: (d_model, d_head)
    Q = x @ W_q  # What am I looking for?
    K = x @ W_k  # What do I contain?
    V = x @ W_v  # What will I send if chosen?

    scale = W_q.shape[1] ** 0.5
    scores = (Q @ K.T) / scale  # (T, T)

    # Causal mask: token i cannot see j > i
    mask = torch.triu(torch.ones(len(x), len(x)), diagonal=1).bool()
    scores = scores.masked_fill(mask, float("-inf"))

    weights = F.softmax(scores, dim=-1)  # (T, T), sums to 1
    return weights @ V                   # (T, d_head)
```

## Q, K, V Metaphor

| | Role | Metaphor |
|-|------|----------|
| Query (Q) | What this token seeks | Search query |
| Key (K) | What each token advertises | Book index |
| Value (V) | Actual content to retrieve | Book content |

## Multi-Head Attention

Run `h` heads in parallel, each with independent weights. Concatenate, project back.

GPT-2 small: 12 heads. GPT-4: ~96 heads.

## Complexity

`Q @ K.T` is O(T²). With T=128K (GPT-4 context): 17B ops per attention layer × 120 layers.  
This is why long contexts are expensive. FlashAttention makes it faster but same math.

*Next: [04 — Transformer](04_transformer.md)*
