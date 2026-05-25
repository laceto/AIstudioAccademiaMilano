# 07 — Studio Playbook

> Every concept in chapters 01-06 has a direct consequence for what we build and price.

## Model Selection (2025)

```
Complex reasoning / long docs?  → claude-opus-4-7  ($15/$75 per 1M)
Balanced quality + speed?       → claude-sonnet-4-6 ($3/$15 per 1M)
Fast, cheap, extraction tasks?  → claude-haiku-4-5  ($0.80/$4 per 1M)
OpenAI ecosystem needed?        → gpt-4o-mini       ($0.15/$0.60 per 1M)
Ultra-fast (<1s, high volume)?  → Groq + llama-3.3-70b ($0.59/$0.79 per 1M)
Text similarity / RAG search?   → text-embedding-3-small ($0.02/1M tokens)
Local / no API key / HF?        → nomic-embed-text or BAAI/bge-large-en-v1.5
```

## Pipeline Model Map

| Agent | Task | Model | Why |
|-------|------|-------|-----|
| Stacy | Intent classification | claude-haiku-4-5 | Fast, cheap, binary decisions |
| Gianni | Technical scoping | claude-sonnet-4-6 | Needs reasoning, not ultra-complex |
| Chiara | Code generation | claude-sonnet-4-6 | Quality + speed balance |
| Marco | Pricing check | claude-haiku-4-5 | Simple table lookup |
| Francesca | Delivery actions | claude-haiku-4-5 | Mostly tool calls |
| Luigi | Escalations | claude-opus-4-7 + extended thinking | High-stakes, needs best reasoning |
| RAG/Synthesizer | Batch synthesis | claude-haiku-4-5 via kitai.batch | 50% batch discount, async |
| LLMClassifier (ISS-012) | Free-text dispenser input | claude-haiku-4-5 | Sub-cent per request, escalate at confidence < 0.8 |

## RAG vs Full Context

```
Full context: 50K tokens → claude-sonnet-4-6 = $0.75/query
RAG (5 chunks): 2K tokens → claude-haiku-4-5  = $0.002/query
Cost reduction: 375×
```

**Studio rule**: always RAG for knowledge retrieval. Use full context only for creative/synthesis tasks.

## Prompt Caching Strategy

Pipeline agents send the same system prompt on every request. Cache it.

```python
# System prompt cached after first call — 90% discount on subsequent calls
system = [
    {
        "type": "text",
        "text": STACY_SYSTEM_PROMPT,        # ~2000 tokens — cache this
        "cache_control": {"type": "ephemeral"}
    }
]
```

Monthly savings estimate: 10 requests/day × 2000-token system prompt × 30 days = 600K tokens.  
Without caching: $0.48/month. With caching: $0.048/month. Not huge alone, scales with volume.

## Prompt Engineering Rules

1. **System prompt = prior.** Every token is paid for on every call. Keep it dense.
2. **Few-shot > instructions.** Show don't tell.
3. **Chain-of-thought for reasoning.** Add "think step by step" for complex logic.
4. **Structured output for data extraction.** Don't parse text — get JSON directly.
5. **Cache stable context.** Anything > 1024 tokens that doesn't change → `cache_control`.

## Structured Output

```python
from pydantic import BaseModel
class InvoiceFields(BaseModel):
    client_name: str
    amount: float

# OpenAI
resp = client.beta.chat.completions.parse(
    model="gpt-4o-mini",
    messages=[{"role": "user", "content": raw_text}],
    response_format=InvoiceFields,
)
fields = resp.choices[0].message.parsed

# Anthropic
resp = client.messages.create(
    model="claude-haiku-4-5-20251001",
    tools=[{"name": "extract", "input_schema": InvoiceFields.model_json_schema()}],
    tool_choice={"type": "tool", "name": "extract"},
    messages=[{"role": "user", "content": raw_text}]
)
fields = resp.content[0].input
```

## HuggingFace Inference at the Studio

With `HF_TOKEN` and `HUGGINGFACE_REPO` set (Chapter env), you can:

```python
import os
from huggingface_hub import InferenceClient

# Serverless inference — no GPU needed, pay per token
client = InferenceClient(token=os.environ["HF_TOKEN"])

result = client.text_generation(
    prompt="Translate to Italian: The invoice is ready.",
    model="meta-llama/Meta-Llama-3-8B-Instruct",
    max_new_tokens=100,
)

# Push a fine-tuned model to your repo
from transformers import AutoModelForCausalLM
model.push_to_hub(os.environ["HUGGINGFACE_REPO"])
```

HF Inference API free tier: ~1000 requests/day. Upgrade to PRO ($9/month) for higher limits.

## Cost Decision Tree

```
Is this a one-time batch job?
  → Yes → Batch API (50% off)
Is the system prompt > 1024 tokens and repeated?
  → Yes → Prompt caching (90% off input)
Is quality the top concern?
  → Yes → claude-opus-4-7
Is speed the top concern?
  → Yes → claude-haiku-4-5 or Groq
Is cost the top concern?
  → Yes → claude-haiku-4-5 + RAG + caching
```

## Further Reading

| Resource | What you learn |
|----------|----------------|
| [nanoGPT](https://github.com/karpathy/nanoGPT) | Full GPT-2 in 300 lines |
| [minbpe](https://github.com/karpathy/minbpe) | BPE tokenizer from scratch |
| [Let's build GPT](https://www.youtube.com/watch?v=kCc8FmEb1nY) | Best 2hr intro ever made |
| Attention Is All You Need (2017) | Original paper — 13 pages |
| [DeepSeek-R1 paper](https://arxiv.org/abs/2501.12948) | GRPO + reasoning emergence |
| [HuggingFace TRL docs](https://huggingface.co/docs/trl) | DPO/GRPO/SFT fine-tuning |

*Next: [08 — Reasoning Models](08_reasoning_models.md)*
