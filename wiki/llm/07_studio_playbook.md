# 07 — Studio Playbook

> Every concept in chapters 01-06 has a direct consequence for what we build and price.

## Model Selection

```
Complex reasoning?          → gpt-4o or claude-sonnet-4-6
Formatting / extraction?    → gpt-4o-mini (10× cheaper)
Ultra-fast (<1s)?           → Groq + llama-3.3-70b
Text similarity / search?   → text-embedding-3-small
Local / no API key?         → all-MiniLM-L6-v2
```

## RAG vs Full Context

```
Full context: 50K tokens → gpt-4o  = $0.125/query
RAG (5 chunks): 2K tokens → gpt-4o-mini = $0.0003/query
Cost reduction: 400×
```

## Prompt Engineering Rules

1. **System prompt = prior.** Every token is paid for on every call. Keep it dense.
2. **Few-shot > instructions.** Show don't tell.
3. **Chain-of-thought for reasoning.** Add "think step by step" for complex logic.

## Structured Output

```python
from pydantic import BaseModel
class InvoiceFields(BaseModel):
    client_name: str
    amount: float

resp = client.beta.chat.completions.parse(
    model="gpt-4o-mini",
    messages=[{"role": "user", "content": raw_text}],
    response_format=InvoiceFields,   # guaranteed valid schema
)
fields = resp.choices[0].message.parsed
```

## Further Reading (Karpathy)

| Resource | What you learn |
|----------|----------------|
| [nanoGPT](https://github.com/karpathy/nanoGPT) | Full GPT-2 in 300 lines |
| [minbpe](https://github.com/karpathy/minbpe) | BPE tokenizer from scratch |
| [Let's build GPT](https://www.youtube.com/watch?v=kCc8FmEb1nY) | Best 2hr intro ever made |
| Attention Is All You Need (2017) | Original paper — 13 pages |
