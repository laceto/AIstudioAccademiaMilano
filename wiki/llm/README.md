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
| 03 | [Attention](03_attention.md) | Tokens talk to each other | GQA + FlashAttention in modern models |
| 04 | [Transformer Architecture](04_transformer.md) | Stack of attention + MLP | RoPE, RMSNorm, MoE — what you rent |
| 05 | [Training & Alignment](05_training.md) | Pretraining → DPO/GRPO | Why models reason and follow instructions |
| 06 | [Inference & Sampling](06_inference.md) | Temperature, caching, batching | Cut costs 90% with prompt caching |
| 07 | [Studio Playbook](07_studio_playbook.md) | Apply all of this here | Ship faster, spend less |
| 08 | [Reasoning Models](08_reasoning_models.md) | Extended thinking, RLVR | When to spend $0.65 on one query |

---

## Karpathy's Key Lessons (Applied Here)

1. **"The best way to understand something is to build it."** → See `wiki/llm/code/`
2. **"Tokens are not words."** → `"ChatGPT" = ["Chat", "G", "PT"]` — 3 tokens
3. **"Attention is just a weighted average."** → 20 lines of Python
4. **"Loss is the compass."** → Cross-entropy on next-token prediction drives everything
5. **"Scale wins."** → GPT-2 (1.5B) → GPT-4 (~1.8T). Same architecture, more parameters.

---

## Quick Reference: Model Costs (2025)

| Model | Input $/1M | Output $/1M | Best for |
|-------|-----------|------------|----------|
| `claude-haiku-4-5` | $0.80 | $4.00 | Stacy, Marco, Francesca — fast ops |
| `claude-sonnet-4-6` | $3.00 | $15.00 | Chiara, Gianni — generation + coding |
| `claude-opus-4-7` | $15.00 | $75.00 | Luigi escalations, extended thinking |
| `gpt-4o-mini` | $0.15 | $0.60 | OpenAI fallback, structured extraction |
| `llama-3.3-70b` (Groq) | $0.59 | $0.79 | Ultra-low latency |
| `text-embedding-3-small` | $0.02 | — | RAG embeddings (OpenAI) |
| `nomic-embed-text` | free | — | RAG embeddings (local/HF) |

*Maintained by: [wiki-curator agent](~/.claude/agents/wiki-curator.md)*  
*Last updated: 2026-05-24*
