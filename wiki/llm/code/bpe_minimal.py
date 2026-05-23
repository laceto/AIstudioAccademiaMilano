"""
bpe_minimal.py — Byte-Pair Encoding tokenizer from scratch (~60 lines).
Inspired by Karpathy's minbpe.
"""

from collections import Counter


def get_pairs(vocab):
    pairs = Counter()
    for symbols, freq in vocab.items():
        for i in range(len(symbols) - 1):
            pairs[(symbols[i], symbols[i + 1])] += freq
    return pairs


def merge_pair(vocab, pair):
    merged = pair[0] + pair[1]
    new_vocab = {}
    for symbols, freq in vocab.items():
        new_syms, i = [], 0
        while i < len(symbols):
            if i < len(symbols) - 1 and (symbols[i], symbols[i + 1]) == pair:
                new_syms.append(merged); i += 2
            else:
                new_syms.append(symbols[i]); i += 1
        new_vocab[tuple(new_syms)] = freq
    return new_vocab


def train_bpe(text, num_merges=20):
    from collections import Counter
    word_freq = Counter(text.lower().split())
    vocab = {tuple(list(w) + ["</w>"]): f for w, f in word_freq.items()}
    rules = []
    for i in range(num_merges):
        pairs = get_pairs(vocab)
        if not pairs: break
        best = pairs.most_common(1)[0][0]
        vocab = merge_pair(vocab, best)
        rules.append(best)
        print(f"Merge {i+1:2d}: {best[0]!r} + {best[1]!r} → {best[0]+best[1]!r}")
    return vocab, rules


if __name__ == "__main__":
    corpus = "the cat sat on the mat the cat ate the rat the mat is flat"
    _, rules = train_bpe(corpus, num_merges=10)
