# 04 — Transformer Architecture

> "The transformer is surprisingly simple. It's embarrassingly a bunch of matrix multiplications."

## One Block

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
        x = x + attn_out          # residual
        x = x + self.mlp(self.ln2(x))  # residual
        return x
```

## Scale

| Model | Layers | d_model | Params |
|-------|--------|---------|--------|
| GPT-2 small | 12 | 768 | 117M |
| LLaMA 3 8B | 32 | 4096 | 8B |
| GPT-4* | ~120 | ~12288 | ~1.8T |

## Why Residuals?

`x_out = x_in + F(x_in)` → gradient always has a path through identity.  
Without residuals: vanishing gradient kills training past ~10 layers.

*Next: [05 — Training](05_training.md)*
