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

*Next: [07 — Studio Playbook](07_studio_playbook.md)*
