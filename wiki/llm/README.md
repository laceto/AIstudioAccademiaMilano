# LLM Wiki — AI Studio Accademia Milano

> Inspired by Andrej Karpathy's "build it from scratch" philosophy.
> Every concept here connects directly to what we ship in this studio.

---

## The Big Picture

A Large Language Model is a function that takes text in and produces text out.
Under the hood it is a stack of matrix multiplications with a sprinkling of non-linearity.

```
User text  →  [Tokenizer]  →  [Embedding]  →  [N × Transformer Blocks]  →  [LM Head]  →  Next token
```

---

## Chapters

| # | Topic | Key idea | Studio connection |
|---|-------|----------|-------------------|
| 01 | [Tokenization](01_tokenization.md) | Text → integers | Every API call starts here |
| 02 | [Embeddings](02_embeddings.md) | Integers → vectors | Powers our RAG retrieval |
| 03 | [Attention](03_attention.md) | Tokens talk to each other | Why GPT-4 understands context |
| 04 | [Transformer Architecture](04_transformer.md) | Stack of attention + MLP | What you rent from OpenAI |
| 05 | [Training & Alignment](05_training.md) | Pretraining → RLHF | Why models are helpful + safe |
| 06 | [Inference & Sampling](06_inference.md) | Temperature, top-k, top-p | Tuning chatbot creativity |
| 07 | [Studio Playbook](07_studio_playbook.md) | Apply all of this here | Ship faster, spend less |

---

## Karpathy's Key Lessons (Applied Here)

1. **"The best way to understand something is to build it."** → See `wiki/llm/code/`
2. **"Tokens are not words."** → `"ChatGPT" = ["Chat", "G", "PT"]` — 3 tokens
3. **"Attention is just a weighted average."** → 20 lines of Python
4. **"Loss is the compass."** → Cross-entropy on next-token prediction drives everything
5. **"Scale wins."** → GPT-2 (1.5B) → GPT-4 (~1.8T). Same architecture.

---

## Quick Reference: Model Costs at the Studio

| Model | Input $/1M | Output $/1M | Best for |
|-------|-----------|------------|----------|
| `gpt-4o-mini` | $0.15 | $0.60 | Most studio tasks |
| `gpt-4o` | $2.50 | $10.00 | Complex reasoning |
| `claude-sonnet-4-6` | $3.00 | $15.00 | Long docs, coding |
| `llama-3.3-70b` (Groq) | $0.59 | $0.79 | Fast + cheap |
| `text-embedding-3-small` | $0.02 | — | RAG embeddings |

*Last updated: 2026-05-23*
