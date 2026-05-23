"""
bpe_minimal.py — Byte-Pair Encoding tokenizer from scratch.

Inspired by Karpathy's minbpe. ~60 lines.
Train a tiny BPE vocabulary on any text.

Usage:
    python -m wiki.llm.code.bpe_minimal
"""

from collections import Counter
from typing import Optional


def get_pairs(vocab: dict[tuple, int]) -> Counter:
    """Count all adjacent symbol pairs across the vocabulary."""
    pairs: Counter = Counter()
    for symbols, freq in vocab.items():
        for i in range(len(symbols) - 1):
            pairs[(symbols[i], symbols[i + 1])] += freq
    return pairs


def merge_pair(vocab: dict[tuple, int], pair: tuple[str, str]) -> dict[tuple, int]:
    """Merge the most frequent pair into a single symbol."""
    new_vocab: dict[tuple, int] = {}
    merged = pair[0] + pair[1]
    for symbols, freq in vocab.items():
        new_symbols: list[str] = []
        i = 0
        while i < len(symbols):
            if i < len(symbols) - 1 and (symbols[i], symbols[i + 1]) == pair:
                new_symbols.append(merged)
                i += 2
            else:
                new_symbols.append(symbols[i])
                i += 1
        new_vocab[tuple(new_symbols)] = freq
    return new_vocab


def train_bpe(text: str, num_merges: int = 20) -> tuple[dict, list]:
    """Train BPE on text. Returns (vocab, merge_rules)."""
    # Start: every word split into characters + end-of-word marker
    word_freq: Counter = Counter(text.lower().split())
    vocab = {tuple(list(word) + ["</w>"]): freq for word, freq in word_freq.items()}

    merge_rules: list[tuple] = []
    for i in range(num_merges):
        pairs = get_pairs(vocab)
        if not pairs:
            break
        best = pairs.most_common(1)[0][0]
        vocab = merge_pair(vocab, best)
        merge_rules.append(best)
        print(f"Merge {i+1:2d}: {best[0]!r} + {best[1]!r} → {best[0]+best[1]!r}")

    return vocab, merge_rules


def tokenize(text: str, merge_rules: list[tuple]) -> list[str]:
    """Apply learned merge rules to new text."""
    tokens: list[str] = []
    for word in text.lower().split():
        symbols = list(word) + ["</w>"]
        for pair in merge_rules:
            merged = pair[0] + pair[1]
            i = 0
            new: list[str] = []
            while i < len(symbols):
                if i < len(symbols) - 1 and (symbols[i], symbols[i + 1]) == pair:
                    new.append(merged)
                    i += 2
                else:
                    new.append(symbols[i])
                    i += 1
            symbols = new
        tokens.extend(symbols)
    return tokens


if __name__ == "__main__":
    corpus = """
    the cat sat on the mat the cat ate the rat
    the rat ran from the cat the mat is flat
    """
    print("=== Training BPE ===")
    vocab, rules = train_bpe(corpus, num_merges=10)
    print()

    test = "the cat sat on the mat"
    print(f"=== Tokenizing: {test!r} ===")
    print(tokenize(test, rules))
