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

## Multi-Head Attention (MHA)

Run `h` heads in parallel, each with independent weights. Concatenate, project back.  
GPT-2 small: 12 heads. GPT-4: ~96 heads.

## Grouped Query Attention (GQA) — Modern Default

Standard MHA: each query head has its own K and V heads → memory-heavy.  
**GQA**: multiple query heads share one K/V pair → 4-8× smaller KV cache.

```
MHA:  Q heads = K heads = V heads = 32   (GPT-2 style)
GQA:  Q heads = 32,  K/V heads = 8       (LLaMA 3, Mistral, Gemma 2)
MQA:  Q heads = 32,  K/V heads = 1       (extreme, early mobile models)
```

Why it matters: KV cache grows linearly with context length and batch size.  
GQA makes 128K+ context windows practical.

## Complexity & FlashAttention

`Q @ K.T` is O(T²) in memory. With T=128K: storing scores needs 128GB.

**FlashAttention 2/3**: never materialises the full (T×T) matrix. Tiles the computation across SRAM. Same math, no approximation, 3-8× faster wall-clock.

```python
# Use automatically in modern PyTorch (2.0+)
with torch.backends.cuda.sdp_kernel(enable_flash=True):
    out = F.scaled_dot_product_attention(Q, K, V, is_causal=True)
```

All recent models (LLaMA 3, Claude, GPT-4o) use FlashAttention internally.

*Next: [04 — Transformer](04_transformer.md)*
