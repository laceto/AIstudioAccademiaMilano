"""
sampling_demo.py — Temperature, top-k, and top-p sampling visualised.

No model needed — we use a synthetic logit distribution.

Usage:
    python -m wiki.llm.code.sampling_demo
"""

import random
from collections import Counter

import numpy as np


def softmax(logits: np.ndarray, temp: float = 1.0) -> np.ndarray:
    scaled = logits / max(temp, 1e-8)
    scaled -= scaled.max()
    e = np.exp(scaled)
    return e / e.sum()


def greedy(logits: np.ndarray) -> int:
    return int(np.argmax(logits))


def temperature_sample(logits: np.ndarray, temp: float = 1.0) -> int:
    probs = softmax(logits, temp)
    return int(np.random.choice(len(probs), p=probs))


def top_k_sample(logits: np.ndarray, k: int = 10, temp: float = 1.0) -> int:
    top_k_idx = np.argsort(logits)[-k:]
    mask = np.full(len(logits), -np.inf)
    mask[top_k_idx] = logits[top_k_idx]
    probs = softmax(mask, temp)
    return int(np.random.choice(len(probs), p=probs))


def top_p_sample(logits: np.ndarray, p: float = 0.9, temp: float = 1.0) -> int:
    probs = softmax(logits, temp)
    sorted_idx = np.argsort(probs)[::-1]
    cumulative = np.cumsum(probs[sorted_idx])
    # Keep tokens until we exceed p
    cutoff = np.searchsorted(cumulative, p) + 1
    nucleus = sorted_idx[:cutoff]
    nucleus_probs = probs[nucleus]
    nucleus_probs /= nucleus_probs.sum()
    chosen = int(np.random.choice(nucleus, p=nucleus_probs))
    return chosen


def run_experiment(logits: np.ndarray, vocab: list[str], n: int = 2000) -> None:
    strategies = {
        "Greedy":       lambda: greedy(logits),
        "Temp=0.3":     lambda: temperature_sample(logits, 0.3),
        "Temp=0.7":     lambda: temperature_sample(logits, 0.7),
        "Temp=1.5":     lambda: temperature_sample(logits, 1.5),
        "Top-K=5":      lambda: top_k_sample(logits, k=5),
        "Top-P=0.9":    lambda: top_p_sample(logits, p=0.9),
    }

    print(f"Vocab: {vocab}")
    print(f"Raw logits: {np.round(logits, 2)}\n")
    print(f"{'Strategy':<14}  Distribution over {n} samples")
    print("-" * 60)

    for name, fn in strategies.items():
        np.random.seed(0)
        counts = Counter(fn() for _ in range(n))
        bar = "  ".join(f"{vocab[i]}:{counts.get(i,0)/n:.0%}" for i in range(len(vocab)))
        print(f"{name:<14}  {bar}")


if __name__ == "__main__":
    # Synthetic next-token distribution
    # Token 0 is most likely ("Paris"), token 4 is a long-tail token
    vocab   = ["Paris", "Rome", "Berlin", "London", "Ulaanbaatar"]
    logits  = np.array([3.5, 2.1, 1.8, 1.6, 0.2])

    run_experiment(logits, vocab)
    print()
    print("Key insight: temperature compresses/expands the distribution.")
    print("Top-K/Top-P truncate the tail before sampling.")
