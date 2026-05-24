# 06 — Inference & Sampling

## Temperature

```python
probs = torch.softmax(logits / temperature, dim=-1)
next_token = torch.multinomial(probs, 1).item()
```

| Temp | Effect | Studio use |
|------|--------|------------|
| 0.1 | Deterministic | Invoice, PDF generation |
| 0.7 | Balanced | Most tasks |
| 1.0 | Raw distribution | Creative writing |

## Top-P (Nucleus) Sampling

Take the smallest set of tokens with cumulative probability ≥ p.  
`top_p=0.9` is the most common production setting.

## Streaming

```python
with st.chat_message("assistant"):
    response = st.write_stream(
        chunk.choices[0].delta.content or ""
        for chunk in client.chat.completions.create(
            model="gpt-4o", messages=messages, stream=True
        )
        if chunk.choices[0].delta.content
    )
```

Each chunk = 1-4 tokens. User sees output immediately.

## KV Cache

Reuse K,V for all previous tokens — only compute new token's K,V on each step.  
Without: O(T²). With: O(T). Long contexts are memory-limited, not compute-limited.

## Prompt Caching — Real Cost Saver (Anthropic)

If the first N tokens of a prompt are identical across calls, Anthropic caches the KV computation.  
**Cache hit: 90% discount on input tokens.**

```python
import anthropic
client = anthropic.Anthropic()

response = client.messages.create(
    model="claude-sonnet-4-6",
    max_tokens=1024,
    system=[
        {
            "type": "text",
            "text": long_system_prompt,          # cached after first call
            "cache_control": {"type": "ephemeral"}
        }
    ],
    messages=[{"role": "user", "content": user_query}]
)
print(response.usage)  # cache_read_input_tokens, cache_creation_input_tokens
```

Cache TTL: 5 minutes (ephemeral). Minimum cacheable block: 1024 tokens.  
**Studio impact**: system prompts + pipeline instructions sent on every request → cache them.

## Speculative Decoding

Use a small "draft" model to generate k tokens, then verify with the large model in one forward pass.  
Net effect: 2-3× throughput improvement with identical output distribution.

```
Draft model (e.g. LLaMA 3 1B):  generates [t1, t2, t3, t4, t5] quickly
Target model (e.g. LLaMA 3 70B): verifies all 5 in one pass, accepts/rejects each
```

Used internally by: Anthropic (claude-haiku drafts for claude-sonnet), Google (PaLM 2).

## Extended Thinking (Chain-of-Thought Internalized)

See Chapter 08 for the full treatment. Quick summary:

```python
response = client.messages.create(
    model="claude-opus-4-7",
    max_tokens=16000,
    thinking={"type": "enabled", "budget_tokens": 10000},
    messages=[{"role": "user", "content": hard_problem}]
)

for block in response.content:
    if block.type == "thinking":
        print("Reasoning:", block.thinking)    # internal scratchpad
    elif block.type == "text":
        print("Answer:", block.text)           # final response
```

Thinking tokens are billed but not displayed to users. Budget: 1024–32000 tokens.

## Batching for Cost

```python
# Process 10 requests at once instead of sequentially
# OpenAI Batch API: 50% cheaper, results within 24h
from openai import OpenAI
client = OpenAI()

batch = client.batches.create(
    input_file_id=uploaded_file.id,
    endpoint="/v1/chat/completions",
    completion_window="24h"
)
```

Use `kitai.batch` (already in studio skills) for the embedding + chat batch pattern.

*Next: [07 — Studio Playbook](07_studio_playbook.md)*
