# 05 — Training & Alignment

## Stage 1: Pretraining

Objective: predict the next token. That's it.

```python
logits  = model(tokens)           # (B, T, vocab_size)
targets = tokens[:, 1:]           # shift by 1
loss    = F.cross_entropy(logits[:, :-1].reshape(-1, vocab_size), targets.reshape(-1))
```

Run over ~10 trillion tokens of internet text. Cost for GPT-4: ~$100M.

## Stage 2: SFT (Supervised Fine-Tuning)

Teaches `User → Assistant` format using thousands of human-written examples.

## Stage 3: RLHF

1. Show humans two responses, pick better one → train reward model
2. PPO: maximise reward − β × KL(policy, ref_policy)

Anthropic variant: RLAIF — AI evaluates AI using a written "Constitution".

## Fine-tuning at the Studio

**RAG vs Fine-tuning decision:**

| Scenario | Use RAG | Fine-tune |
|----------|---------|----------|
| Knowledge changes frequently | ✅ | ❌ |
| Style / tone / format | ❌ | ✅ |
| Fast iteration | ✅ | ❌ |

**Studio default: RAG first.**

*Next: [06 — Inference](06_inference.md)*
