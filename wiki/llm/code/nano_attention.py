"""
nano_attention.py — Self-attention from scratch in numpy.
Inspired by Karpathy's nanoGPT.
"""

import numpy as np


def softmax(x, axis=-1):
    x = x - x.max(axis=axis, keepdims=True)
    e = np.exp(x)
    return e / e.sum(axis=axis, keepdims=True)


def self_attention(X, W_q, W_k, W_v, causal=True):
    T, d_model = X.shape
    d_head = W_q.shape[1]
    Q, K, V = X @ W_q, X @ W_k, X @ W_v
    scores = Q @ K.T / d_head**0.5
    if causal:
        mask = np.triu(np.ones((T, T)), k=1).astype(bool)
        scores[mask] = -1e9
    return softmax(scores) @ V


if __name__ == "__main__":
    np.random.seed(42)
    T, d, h = 6, 8, 4
    X = np.random.randn(T, d)
    W_q = np.random.randn(d, h) * 0.1
    W_k = np.random.randn(d, h) * 0.1
    W_v = np.random.randn(d, h) * 0.1
    out = self_attention(X, W_q, W_k, W_v)
    print(f"Output shape: {out.shape}")  # (6, 4)
    print("Attention is just a weighted average.")
