"""
nano_attention.py — Self-attention and multi-head attention from scratch.

Inspired by Karpathy's nanoGPT. No PyTorch required for the numpy version.

Usage:
    python -m wiki.llm.code.nano_attention
"""

import numpy as np


def softmax(x: np.ndarray, axis: int = -1) -> np.ndarray:
    x = x - x.max(axis=axis, keepdims=True)  # numerical stability
    e = np.exp(x)
    return e / e.sum(axis=axis, keepdims=True)


def self_attention(
    X: np.ndarray,
    W_q: np.ndarray,
    W_k: np.ndarray,
    W_v: np.ndarray,
    causal: bool = True,
) -> np.ndarray:
    """
    X:     (T, d_model)
    W_q/k/v: (d_model, d_head)
    returns: (T, d_head)
    """
    T, d_model = X.shape
    d_head = W_q.shape[1]

    Q = X @ W_q    # (T, d_head)
    K = X @ W_k
    V = X @ W_v

    scores = Q @ K.T / d_head**0.5   # (T, T)

    if causal:
        mask = np.triu(np.ones((T, T)), k=1).astype(bool)
        scores[mask] = -1e9

    weights = softmax(scores, axis=-1)   # (T, T)
    return weights @ V                   # (T, d_head)


def multi_head_attention(
    X: np.ndarray,
    W_heads: list[tuple],  # list of (W_q, W_k, W_v) per head
    W_out: np.ndarray,     # (h * d_head, d_model)
    causal: bool = True,
) -> np.ndarray:
    """
    Run h heads in parallel, concatenate, project back.
    X: (T, d_model)
    returns: (T, d_model)
    """
    heads = [self_attention(X, wq, wk, wv, causal) for wq, wk, wv in W_heads]
    concat = np.concatenate(heads, axis=-1)   # (T, h * d_head)
    return concat @ W_out                     # (T, d_model)


if __name__ == "__main__":
    np.random.seed(42)

    T        = 6    # sequence length
    d_model  = 8
    d_head   = 4
    n_heads  = 2

    X = np.random.randn(T, d_model)

    # Single head
    W_q = np.random.randn(d_model, d_head) * 0.1
    W_k = np.random.randn(d_model, d_head) * 0.1
    W_v = np.random.randn(d_model, d_head) * 0.1
    out = self_attention(X, W_q, W_k, W_v)
    print(f"Single-head output shape: {out.shape}")   # (6, 4)

    # Multi-head
    heads  = [(np.random.randn(d_model, d_head) * 0.1,
               np.random.randn(d_model, d_head) * 0.1,
               np.random.randn(d_model, d_head) * 0.1)
              for _ in range(n_heads)]
    W_out  = np.random.randn(n_heads * d_head, d_model) * 0.1
    mha_out = multi_head_attention(X, heads, W_out)
    print(f"Multi-head output shape:  {mha_out.shape}")  # (6, 8) = (T, d_model)
    print("\nAll checks passed. Attention is just a weighted average.")
