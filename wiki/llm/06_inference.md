# 06 — Inference & Sampling

> "The model outputs a probability distribution over 50,257 tokens.
> Sampling is choosing from that distribution."

---

## The Output: Logits → Probabilities

```
Last token hidden state (d_model,)
        ↓
   Linear layer (LM Head)     W: (d_model, vocab_size)
        ↓
   Logits (vocab_size,)        raw unnormalised scores
        ↓
   Softmax
        ↓
   Probabilities (vocab_size,)  sum to 1.0
```

```python
logits = model(tokens)[-1]          # last position only
probs  = torch.softmax(logits, dim=-1)

# Top 5 candidates
top5_ids   = torch.topk(probs, 5).indices
top5_probs = torch.topk(probs, 5).values
for id, p in zip(top5_ids, top5_probs):
    print(f"{enc.decode([id.item()])!r:20s} {p.item():.4f}")
# ' Paris'               0.3821
# ' Rome'                0.1204
# ' Berlin'              0.0891
# ' London'              0.0743
# ' Madrid'              0.0521
```

---

## Temperature

Controls the sharpness of the distribution.

```python
def temperature_sample(logits: torch.Tensor, temp: float) -> int:
    scaled = logits / temp          # divide BEFORE softmax
    probs  = torch.softmax(scaled, dim=-1)
    return torch.multinomial(probs, 1).item()
```

| Temperature | Effect | Use case |
|-------------|--------|----------|
| 0.0 | Greedy (always max) | Deterministic, factual |
| 0.3 | Focused, less creative | Code generation |
| 0.7 | Balanced | Most chat tasks |
| 1.0 | Raw model distribution | Creative writing |
| 1.5+ | Wild, often incoherent | Brainstorming, never production |

**Studio defaults by product:**
- Invoice / PDF generation: `temp=0.1` (deterministic formatting)
- Strategic reports: `temp=0.7` (insight + coherence)
- Chatbot: `temp=0.8` (natural conversation)

---

## Top-K Sampling

Only sample from the K most likely tokens. Ignore the rest.

```python
def top_k_sample(logits, k=50, temp=0.7):
    top_k_values, _ = torch.topk(logits, k)
    # Zero out everything below the k-th threshold
    indices_to_remove = logits < top_k_values[-1]
    logits[indices_to_remove] = float("-inf")
    probs = torch.softmax(logits / temp, dim=-1)
    return torch.multinomial(probs, 1).item()
```

Karpathy: *"top_k=200 is almost always fine. The long tail of 50k tokens is noise anyway."*

---

## Top-P (Nucleus) Sampling

Dynamic K: take the smallest set of tokens whose cumulative probability ≥ p.

```python
def top_p_sample(logits, p=0.9, temp=0.7):
    probs = torch.softmax(logits / temp, dim=-1)
    sorted_probs, sorted_idx = torch.sort(probs, descending=True)
    cumulative = torch.cumsum(sorted_probs, dim=-1)
    # Remove tokens once cumulative prob exceeds p
    remove = cumulative - sorted_probs > p
    sorted_probs[remove] = 0.0
    sorted_probs /= sorted_probs.sum()  # renormalise
    chosen = torch.multinomial(sorted_probs, 1)
    return sorted_idx[chosen].item()
```

`top_p=0.9` is the most common production setting.  
When the model is confident, nucleus is small (1-3 tokens).  
When uncertain, nucleus grows to include more options.

---

## Streaming

The model generates one token at a time. Streaming shows each token as it arrives.

```python
# Our chatbot (deliverables/2026-05-23_005_chatbot/app.py)
from openai import OpenAI
import streamlit as st

client = OpenAI(api_key=st.secrets["OPENAI_API_KEY"])

with st.chat_message("assistant"):
    response = st.write_stream(
        chunk.choices[0].delta.content or ""
        for chunk in client.chat.completions.create(
            model="gpt-4o",
            messages=messages,
            stream=True,            # ← one token at a time
        )
        if chunk.choices[0].delta.content
    )
```

Each `chunk` contains typically 1-4 tokens. User sees output immediately.  
Latency: time-to-first-token (TTFT) matters more than total time.

---

## Speculative Decoding (Advanced)

Slow model + fast model combo:
1. Draft model (small, fast) generates K tokens
2. Target model (large) verifies all K in one pass
3. Accept matching tokens, reject divergence
4. Net result: 2-3× faster with identical output distribution

Used by Groq hardware, some OpenAI optimisations. Transparent to the API user.

---

## KV Cache

The key optimisation that makes inference practical:

```
First call:   tokens [1..T]    → compute K,V for all T tokens
Next call:    token [T+1]      → only compute K,V for new token
                                 reuse K,V for tokens [1..T] from cache
```

Without KV cache: O(T²) per token generated.  
With KV cache: O(T) per token — the dominant cost shifts to memory bandwidth.

This is why long context is expensive in *memory* (GPU RAM) not just compute.

---

*Next: [07 — Studio Playbook](07_studio_playbook.md)*
