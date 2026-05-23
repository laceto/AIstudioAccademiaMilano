"""
sampling_demo.py — Temperature, top-k, top-p sampling visualised in numpy.
"""

from collections import Counter
import numpy as np


def softmax(logits, temp=1.0):
    scaled = logits / max(temp, 1e-8)
    scaled -= scaled.max()
    e = np.exp(scaled)
    return e / e.sum()


def temperature_sample(logits, temp=1.0):
    return int(np.random.choice(len(logits), p=softmax(logits, temp)))


def top_k_sample(logits, k=10, temp=1.0):
    mask = np.full(len(logits), -np.inf)
    mask[np.argsort(logits)[-k:]] = logits[np.argsort(logits)[-k:]]
    return int(np.random.choice(len(logits), p=softmax(mask, temp)))


def top_p_sample(logits, p=0.9, temp=1.0):
    probs = softmax(logits, temp)
    idx = np.argsort(probs)[::-1]
    cut = np.searchsorted(np.cumsum(probs[idx]), p) + 1
    nucleus = idx[:cut]
    nprobs = probs[nucleus] / probs[nucleus].sum()
    return int(np.random.choice(nucleus, p=nprobs))


if __name__ == "__main__":
    vocab = ["Paris", "Rome", "Berlin", "London", "Ulaanbaatar"]
    logits = np.array([3.5, 2.1, 1.8, 1.6, 0.2])
    np.random.seed(0)
    n = 1000
    for name, fn in [("Greedy", lambda: int(np.argmax(logits))),
                     ("Temp=0.3", lambda: temperature_sample(logits, 0.3)),
                     ("Temp=1.0", lambda: temperature_sample(logits, 1.0)),
                     ("Top-P=0.9", lambda: top_p_sample(logits, 0.9))]:
        counts = Counter(fn() for _ in range(n))
        bar = "  ".join(f"{vocab[i]}:{counts.get(i,0)/n:.0%}" for i in range(len(vocab)))
        print(f"{name:<12} {bar}")
