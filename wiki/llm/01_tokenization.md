# 01 — Tokenization

> "The model never sees text. It sees a list of integers."
> — Karpathy, *Let's build the GPT Tokenizer*

---

## What Is a Token?

A token is a chunk of text that the model treats as an atomic unit.  
It is **not** a word, character, or letter — it is something in between.

```
Text:   "Hello, world!"
Tokens: ["Hello", ",", " world", "!"]
IDs:    [15496, 11, 995, 0]          ← what the model actually processes
```

---

## Why Not Characters?

If every character were a token, the sequence `"Hello, world!"` would be 13 tokens.  
A 1000-word document would be ~5000 tokens.  
Transformers have quadratic attention cost → short sequences win.

## Why Not Words?

Vocabulary would be millions of entries.  
`"running"`, `"runs"`, `"ran"` would each be separate, unrelated tokens.  
Out-of-vocabulary words (code, names, emoji) would fail silently.

## Byte-Pair Encoding (BPE) — The Karpathy Way

BPE is a compression algorithm applied to text.

```
Step 1: Start with characters as tokens
        ["h", "e", "l", "l", "o"]

Step 2: Count all adjacent pairs
        (h,e)=1, (e,l)=1, (l,l)=1, (l,o)=1

Step 3: Merge the most frequent pair → new token
        "ll" is added to vocabulary
        ["h", "e", "ll", "o"]

Step 4: Repeat until vocabulary size target (e.g. 50,257 for GPT-2)
```

**Result:** Common subwords (`" the"`, `"ing"`, `"tion"`) become single tokens.  
Rare words get split into pieces.  Code gets weird tokenization.

---

## Try It: tiktoken

```python
import tiktoken

enc = tiktoken.get_encoding("cl100k_base")  # GPT-4 tokenizer

text = "AI Studio Accademia Milano builds digital products"
tokens = enc.encode(text)
print(tokens)          # [15836, 19074, 17559, 54, 9350, 14390, 12045, 3956, 7186]
print(len(tokens))     # 9 tokens for 7 words

# Decode back
print(enc.decode(tokens))  # "AI Studio Accademia Milano builds digital products"

# Token by token
for t in tokens:
    print(repr(enc.decode([t])))
# 'AI'
# ' Studio'
# ' Acc'
# 'ademia'
# ' Milan'
# 'o'
# ' builds'
# ' digital'
# ' products'
```

Notice: `"Accademia"` → 2 tokens. `"Milano"` → 2 tokens.  
Italian proper nouns are rare in training data → more tokens per word.

---

## Tokenization Surprises (Karpathy's Gotchas)

```python
# Numbers
enc.encode("100")     # [1041]   — 1 token
enc.encode("1000")    # [1041, 15]  — wait, same start?  model sees patterns
enc.encode("10000")   # [1041, 931]  each digit group is variable

# Code
enc.encode("def hello():")  # [755, 24748, 90052]

# Emoji — expensive!
enc.encode("🤖")  # [9468, 234, 235]  — 3 tokens for one character!
```

**Rule of thumb:** ~1 token per 4 characters in English. 2-3× more for other languages.

---

## Studio Impact

| Product | Typical tokens | Cost at gpt-4o-mini |
|---------|---------------|----------------------|
| 1-page strategic report prompt | ~2,000 in + ~1,000 out | $0.0009 |
| Invoice generation | ~500 in + ~200 out | $0.0002 |
| Full RAG query (5 chunks) | ~3,000 in + ~500 out | $0.0009 |
| System prompt (100 words) | ~130 tokens | Fixed overhead per call |

**Always count tokens before pricing.** Marco uses `tiktoken` in every cost estimate.

---

## Build It: Minimal BPE in Python

See [`code/bpe_minimal.py`](code/bpe_minimal.py) — 60 lines, trains a tiny BPE tokenizer from scratch.

---

*Next: [02 — Embeddings](02_embeddings.md) — how tokens become meaning*
