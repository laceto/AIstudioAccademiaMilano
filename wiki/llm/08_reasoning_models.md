# 08 — Reasoning Models

> "The model doesn't answer. It thinks first, then answers."

## What Changed

Standard LLMs: input tokens → one forward pass per output token → answer.  
Reasoning models: input tokens → many forward passes of *internal scratchpad* → answer.

The scratchpad is called **thinking tokens**, **chain-of-thought**, or **extended thinking** depending on the vendor. The math is the same attention mechanism from Chapter 03 — just applied to intermediate reasoning steps before committing to an output.

## The Four Reasoning Systems (2025)

| Model | Maker | Approach | Thinking visible? |
|-------|-------|----------|-------------------|
| o3 | OpenAI | Internal CoT, RLVR | No (hidden) |
| o4-mini | OpenAI | Smaller, faster o3 | No |
| claude-opus-4-7 (extended thinking) | Anthropic | Visible thinking blocks | Yes |
| DeepSeek-R1 | DeepSeek | GRPO on verifiable tasks | Yes (`<think>` tags) |

## How It Emerged: DeepSeek-R1

DeepSeek trained on math and code with GRPO (Chapter 05). Reward: answer correct or not.  
No human-labelled reasoning chains. **Chain-of-thought emerged on its own** — the model learned that "thinking out loud" before answering improved the reward signal.

Key finding: you don't need to teach reasoning. You need to reward correct answers on hard problems. The model figures out reasoning as a strategy.

## Claude Extended Thinking

```python
import anthropic
client = anthropic.Anthropic()

response = client.messages.create(
    model="claude-opus-4-7",
    max_tokens=16000,
    thinking={
        "type": "enabled",
        "budget_tokens": 10000    # max tokens for internal reasoning
    },
    messages=[{
        "role": "user",
        "content": "A client wants a RAG system that costs <€50/month at 10K queries/day. Design it."
    }]
)

for block in response.content:
    if block.type == "thinking":
        print("=== Claude's reasoning ===")
        print(block.thinking)      # full scratchpad — visible to you, not to end user
    elif block.type == "text":
        print("=== Final answer ===")
        print(block.text)
```

**Budget tokens**: 1024 minimum, 32000 maximum. More budget = better on hard problems, more expensive.  
**Billing**: thinking tokens billed as output tokens (same rate as text).

## When to Use Extended Thinking

| Task | Standard | Extended thinking |
|------|----------|------------------|
| Extract invoice fields | ✅ | Overkill |
| Write a LinkedIn post | ✅ | Overkill |
| Multi-step architecture decision | ✅ (usually ok) | ✅ (better) |
| Debug a complex multi-agent bug | ❌ (often wrong) | ✅ |
| Price an unknown product type | ❌ | ✅ (less likely to guess) |
| Math / financial modelling | ❌ | ✅ |

**Studio rule**: Use extended thinking when Luigi is reviewing escalations, Marco models complex pricing, or Technical Auditor assesses multi-system risk.

## RLVR — Reinforcement Learning with Verifiable Rewards

The training recipe behind o3 and DeepSeek-R1:

```
1. Generate k responses per problem (k=8 to 64)
2. Score each: 1 if correct, 0 if wrong (math answer, code compiles, logic puzzle)
3. No reward model needed — the problem IS the reward signal
4. Update policy to increase probability of high-scoring responses
5. Repeat on millions of problems
```

The key: problems must have **verifiable ground truth**. Math, code, formal logic, chess.  
This is GRPO (Chapter 05) applied at massive scale with hard problems.

## Practical Cost Model

```
Extended thinking example (claude-opus-4-7):
  System prompt:         500 tokens in   → $0.0075
  User query:           200 tokens in    → $0.0030
  Thinking:           8,000 tokens out   → $0.6000
  Answer:               500 tokens out   → $0.0375
  Total per escalation: ~$0.65

Non-thinking (claude-haiku-4-5):
  Same query, no thinking, answer only: ~$0.002

Use thinking only when the decision is worth $0.65 to get right.
```

## Streaming Thinking

```python
with client.messages.stream(
    model="claude-opus-4-7",
    max_tokens=8000,
    thinking={"type": "enabled", "budget_tokens": 5000},
    messages=[{"role": "user", "content": problem}]
) as stream:
    for event in stream:
        if hasattr(event, "type"):
            if event.type == "content_block_start":
                if event.content_block.type == "thinking":
                    print("\n[thinking] ", end="", flush=True)
                elif event.content_block.type == "text":
                    print("\n[answer] ", end="", flush=True)
            elif event.type == "content_block_delta":
                if hasattr(event.delta, "thinking"):
                    print(event.delta.thinking, end="", flush=True)
                elif hasattr(event.delta, "text"):
                    print(event.delta.text, end="", flush=True)
```

## Further Reading

| Resource | What you learn |
|----------|----------------|
| [DeepSeek-R1 paper](https://arxiv.org/abs/2501.12948) | GRPO + emergent CoT |
| [Anthropic extended thinking docs](https://docs.anthropic.com/en/docs/build-with-claude/extended-thinking) | API reference |
| [OpenAI o3 system card](https://openai.com/index/openai-o3-system-card/) | o3 capabilities |
| [Scaling LLM Test-Time Compute (DeepMind)](https://arxiv.org/abs/2408.03314) | Theory behind thinking tokens |
