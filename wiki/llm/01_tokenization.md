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

## Tokenizer Landscape (2025)

| Tokenizer | Vocab size | Used by | Python library |
|-----------|-----------|---------|----------------|
| `cl100k_base` | 100,277 | GPT-4, Claude (approx) | `tiktoken` |
| `o200k_base` | 200,000 | GPT-4o, o1, o3 | `tiktoken` |
| LLaMA 3 BPE | 128,000 | LLaMA 3, Mistral | `transformers` |
| Gemma 2 | 256,000 | Gemma 2, PaliGemma | `transformers` |

Claude uses its own BPE (not public). `cl100k_base` is a close approximation for budgeting.

```python
# HuggingFace tokenizer for any open model
from transformers import AutoTokenizer
tok = AutoTokenizer.from_pretrained("meta-llama/Meta-Llama-3-8B")
tokens = tok.encode("AI Studio Accademia Milano")
print(len(tokens))
```

## Rule of Thumb
~1 token per 4 chars in English. 2-3× more for other languages.  
Code: roughly 1 token per 3 chars. JSON: very expensive (brackets, quotes all count).

## Studio Token Budget

| Product | Typical tokens | claude-haiku-4-5 cost | gpt-4o-mini cost |
|---------|---------------|----------------------|------------------|
| Strategic report | ~2,000 in + ~1,000 out | $0.00028 | $0.0009 |
| Invoice generation | ~500 in + ~200 out | $0.00007 | $0.0002 |
| RAG query (5 chunks) | ~3,000 in + ~500 out | $0.00038 | $0.0009 |
| LinkedIn post (D009) | ~800 in + ~300 out | $0.00011 | $0.0003 |

*Next: [02 — Embeddings](02_embeddings.md)*
