# 01 — Tokenization

> "The model never sees text. It sees a list of integers."
> — Karpathy, *Let's build the GPT Tokenizer*

## What Is a Token?

A token is a chunk of text — not a word, character, or letter. Something in between.

```
Text:   "Hello, world!"
Tokens: ["Hello", ",", " world", "!"]
IDs:    [15496, 11, 995, 0]
```

## Byte-Pair Encoding (BPE)

BPE is compression applied to text. Start with characters, merge the most frequent pair repeatedly.

```
Step 1: ["h","e","l","l","o"]  →  count pairs  →  merge most frequent
Step 2: "ll" becomes one token
Step 3: repeat until vocab_size = 50,257 (GPT-2) or 100,277 (GPT-4)
```

## Try It

```python
import tiktoken
enc = tiktoken.get_encoding("cl100k_base")  # GPT-4 tokenizer

text = "AI Studio Accademia Milano"
tokens = enc.encode(text)
print(tokens)       # [15836, 19074, 17559, 54, 9350, 14390]
print(len(tokens))  # 6 tokens for 4 words
```

Notice: `"Accademia"` → 2 tokens, `"Milano"` → 2 tokens. Italian proper nouns are rare in training data.

## Rule of Thumb
~1 token per 4 chars in English. 2-3× more for other languages.

## Studio Token Budget

| Product | Typical tokens | gpt-4o-mini cost |
|---------|---------------|------------------|
| Strategic report prompt | ~2,000 in + ~1,000 out | $0.0009 |
| Invoice generation | ~500 in + ~200 out | $0.0002 |
| RAG query (5 chunks) | ~3,000 in + ~500 out | $0.0009 |

*Next: [02 — Embeddings](02_embeddings.md)*
