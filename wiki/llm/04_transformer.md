# 04 — Transformer Architecture

> "The transformer is surprisingly simple. It's embarrassingly a bunch of matrix multiplications."

## One Block (original 2017)

```python
class TransformerBlock(nn.Module):
    def __init__(self, d_model, n_heads, d_ff):
        super().__init__()
        self.ln1  = nn.LayerNorm(d_model)
        self.attn = nn.MultiheadAttention(d_model, n_heads, batch_first=True)
        self.ln2  = nn.LayerNorm(d_model)
        self.mlp  = nn.Sequential(nn.Linear(d_model, d_ff), nn.GELU(), nn.Linear(d_ff, d_model))

    def forward(self, x, mask=None):
        attn_out, _ = self.attn(self.ln1(x), self.ln1(x), self.ln1(x), is_causal=True)
        x = x + attn_out
        x = x + self.mlp(self.ln2(x))
        return x
```

## Modern Deviations (LLaMA / Mistral style)

Three changes from the 2017 paper that every production model now uses:

### 1. RMSNorm instead of LayerNorm
```python
class RMSNorm(nn.Module):
    def forward(self, x):
        return x / x.pow(2).mean(-1, keepdim=True).add(1e-8).sqrt() * self.weight
```
Faster, no mean subtraction. LLaMA, Mistral, Gemma all use it.

### 2. SwiGLU instead of GELU
```python
def swiglu(x, W1, W2, W3):
    return F.silu(x @ W1) * (x @ W2)  # gating — then project with W3
```
Requires 3 weight matrices instead of 2 but consistently outperforms GELU. Used in LLaMA, PaLM, Gemma.

### 3. RoPE — Rotary Position Embeddings
Encode position by rotating Q and K vectors. No learned position table — works for arbitrarily long sequences.

```python
def apply_rope(x, cos, sin, position_ids):
    # rotate pairs of dimensions by position-dependent angle
    x1, x2 = x[..., ::2], x[..., 1::2]
    return torch.cat([x1 * cos - x2 * sin, x1 * sin + x2 * cos], dim=-1)
```

Used by: LLaMA 3, Mistral, Qwen, DeepSeek, Phi. Not used by GPT-4 (uses learned absolute positions).

## Scale

| Model | Layers | d_model | Heads | Params | Context |
|-------|--------|---------|-------|--------|---------|
| GPT-2 small | 12 | 768 | 12 | 117M | 1K |
| LLaMA 3 8B | 32 | 4096 | 32 (GQA:8) | 8B | 128K |
| Mistral 7B | 32 | 4096 | 32 (GQA:8) | 7B | 32K |
| LLaMA 3 70B | 80 | 8192 | 64 (GQA:8) | 70B | 128K |
| GPT-4* | ~120 | ~12288 | ~96 | ~1.8T (MoE) | 128K |

## Mixture of Experts (MoE)

Dense model: every token goes through every FFN neuron.  
**MoE**: each token is routed to only 2-4 of N expert FFNs. 8× more parameters, same compute.

```
GPT-4: ~1.8T params, ~220B active per token (8 experts / token)
Mixtral 8×7B: 46B params, 12B active per token
DeepSeek-V3: 671B params, 37B active per token
```

The router is a small linear layer that selects experts per token. Simple in theory, hard to train stably (expert collapse is real).

## Why Residuals?

`x_out = x_in + F(x_in)` → gradient always has a path through identity.  
Without residuals: vanishing gradient kills training past ~10 layers.

*Next: [05 — Training](05_training.md)*
