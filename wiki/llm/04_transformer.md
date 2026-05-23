# 04 — Transformer Architecture

> "The transformer is surprisingly simple. It's embarrassingly a bunch of matrix multiplications."
> — Karpathy

---

## Full Forward Pass

```
Input tokens [t₁, t₂, ..., tₙ]
      ↓
[Token Embedding] + [Position Embedding]
      ↓
┌─────────────────────────────────────┐
│  Transformer Block × N              │
│  ┌──────────────────────────────┐   │
│  │  LayerNorm                  │   │
│  │  Multi-Head Self-Attention  │   │
│  │  + Residual connection      │   │
│  ├──────────────────────────────┤   │
│  │  LayerNorm                  │   │
│  │  Feed-Forward Network (MLP) │   │
│  │  + Residual connection      │   │
│  └──────────────────────────────┘   │
└─────────────────────────────────────┘
      ↓
[LayerNorm]
      ↓
[LM Head: linear → vocab_size]
      ↓
[Softmax → probability over next token]
```

---

## The Transformer Block

```python
import torch
import torch.nn as nn

class TransformerBlock(nn.Module):
    def __init__(self, d_model: int, n_heads: int, d_ff: int):
        super().__init__()
        self.ln1  = nn.LayerNorm(d_model)
        self.attn = nn.MultiheadAttention(d_model, n_heads, batch_first=True)
        self.ln2  = nn.LayerNorm(d_model)
        self.mlp  = nn.Sequential(
            nn.Linear(d_model, d_ff),
            nn.GELU(),             # not ReLU — GELU is standard post-2019
            nn.Linear(d_ff, d_model),
        )

    def forward(self, x, mask=None):
        # Attention sub-layer with residual
        attn_out, _ = self.attn(self.ln1(x), self.ln1(x), self.ln1(x),
                                attn_mask=mask, is_causal=True)
        x = x + attn_out            # residual

        # MLP sub-layer with residual
        x = x + self.mlp(self.ln2(x))  # residual
        return x
```

Two residuals per block. That's the "highway" that lets gradients flow through dozens of layers.

---

## The Feed-Forward Network (MLP)

Often overlooked. It's 2/3 of the parameters.

```
d_ff = 4 × d_model   (standard ratio)

GPT-2 small:  d_model=768,  d_ff=3072
GPT-4:        d_model=12288, d_ff=49152
```

The MLP operates **independently on each token position** — no cross-token communication.  
Attention handles *where* to look. MLP handles *what* to compute once you know where.

Karpathy's take: the MLP is the "memory" of the model. It stores factual associations  
(`Paris → France → capital`) learned during pretraining.

---

## LayerNorm (not BatchNorm)

```python
# BatchNorm: normalise across the batch dimension — breaks for batch_size=1
# LayerNorm: normalise across the feature dimension — works at any batch size

ln = nn.LayerNorm(768)
x_normed = ln(x)   # zero mean, unit variance per token
```

Applied *before* attention (Pre-LN) in modern models — more stable training.

---

## Scale Reference

| Model | Layers | d_model | Heads | d_ff | Params |
|-------|--------|---------|-------|------|--------|
| GPT-2 small | 12 | 768 | 12 | 3072 | 117M |
| GPT-2 XL | 48 | 1600 | 25 | 6400 | 1.5B |
| LLaMA 3 8B | 32 | 4096 | 32 | 14336 | 8B |
| GPT-4* | ~120 | ~12288 | ~96 | ~49152 | ~1.8T |
| Claude 3.5 Sonnet* | unknown | unknown | unknown | unknown | unknown |

*Estimated / leaked — Anthropic/OpenAI do not confirm architecture details.

---

## GELU Activation

```python
import torch
import torch.nn.functional as F
import matplotlib.pyplot as plt

x = torch.linspace(-4, 4, 100)

plt.plot(x, F.relu(x),  label="ReLU")
plt.plot(x, F.gelu(x),  label="GELU")  # smooth, nonzero for x<0
plt.legend()
```

GELU ≈ `x * sigmoid(1.702 * x)`.  
It "gates" the input stochastically — more expressive than ReLU.  
Used in GPT-2 onward. GPT-4, LLaMA 2+, Claude all use it (or SwiGLU variant).

---

## Residual Connections — Why They Matter

Without residuals: gradient signal decays exponentially through 100+ layers → vanishing gradient.  
With residuals: gradient highways. `∂loss/∂x_early ≥ 1` is always achievable.

```
x_out = x_in + F(x_in)        ← F can be near-zero, path through x_in is always open
∂x_out/∂x_in = 1 + ∂F/∂x_in  ← at least 1, never zero
```

This is why we can train 100+ layer networks at all.

---

*Next: [05 — Training & Alignment](05_training.md)*
