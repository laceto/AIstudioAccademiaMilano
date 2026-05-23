# 07 — Studio Playbook: Applying LLM Theory Here

> Every concept in chapters 01–06 has a direct consequence for what we build and price.

---

## The Studio's LLM Stack

```
┌─────────────────────────────────────────────────────┐
│  User Request (natural language)                    │
│           ↓                                         │
│  [Stacy] Intent classification                      │
│           ↓                                         │
│  [Gianni] Technical scoping + prompt engineering    │
│           ↓                                         │
│  [Chiara] LLM call → structured output              │
│           │                                         │
│           ├── GPT-4o for reasoning                  │
│           ├── gpt-4o-mini for formatting            │
│           └── text-embedding-3-small for RAG        │
│           ↓                                         │
│  [Stacy QA] Validation (disclaimer, format, price)  │
│           ↓                                         │
│  [Marco] Cost accounting + invoice                  │
│           ↓                                         │
│  [Francesca] Delivery                               │
└─────────────────────────────────────────────────────┘
```

---

## Prompt Engineering Principles

### 1. System Prompt = Prior

The system prompt shifts the entire probability distribution.  
Every token of system prompt is paid for on every call.

```python
# Bad: verbose, repeating obvious things
system = """
You are a helpful AI assistant. Your goal is to help users.
Please be helpful and provide good responses.
Make sure your answers are accurate and relevant.
"""

# Good: dense signal, specific persona
system = """
You are Chiara, AI Studio Accademia Milano's delivery specialist.
Output: structured Markdown only. No apologies. No filler.
Italian legal disclaimer required on all advisory outputs.
"""
```

### 2. Few-Shot Examples > Instructions

```python
# Telling the model is weak. Showing is strong.
messages = [
    {"role": "system",    "content": "Extract invoice fields as JSON."},
    {"role": "user",      "content": "Invoice for 500€ to Acme Srl for web design."},
    {"role": "assistant", "content": '{"client": "Acme Srl", "amount": 500, "service": "web design"}'},
    {"role": "user",      "content": actual_invoice_text},  # now the real call
]
```

### 3. Chain-of-Thought for Reasoning

```
Bad:  "Evaluate if this request requires risk agent review."
Good: "Evaluate if this request requires risk agent review.
       Think step by step:
       1. Does it involve financial advice?
       2. Does it involve external data access?
       3. Does it involve user credentials?
       Then output YES or NO."
```

---

## RAG at the Studio (Connecting ch.02 + ch.03)

Why RAG beats stuffing everything in context:

```
Full context approach:  dump 50K tokens of codebase → gpt-4o
Cost: 50,000 × $2.50/1M = $0.125 per query

RAG approach: retrieve 5 chunks (2,000 tokens) → gpt-4o-mini
Cost: 2,000 × $0.15/1M = $0.0003 per query

Cost reduction: 400×
Quality: often better (focused context, less distraction)
```

Pipeline in production:
```bash
# Build once
python -m scripts.embed_index

# Query
python -m scripts.retrieve "how does Marco price unknown products?" --top-k 5
python -m scripts.rag_chat "explain the 6-agent pipeline"
```

---

## Token Budget by Product

| Product | System | User | Response | Model | Cost |
|---------|--------|------|----------|-------|------|
| Static website | 200 | 300 | 3000 | gpt-4o-mini | €0.002 |
| Invoice PDF | 150 | 400 | 800 | gpt-4o-mini | €0.0002 |
| Strategic report | 400 | 2000 (RAG) | 6000 | gpt-4o | €0.09 |
| Chatbot session (avg 20 turns) | 100 | 8000 | 4000 | gpt-4o-mini | €0.002 |
| RAG knowledge query | 200 | 3000 | 1000 | gpt-4o-mini | €0.0006 |

Studio margin on all products: >90%. LLM cost is not the bottleneck.

---

## Structured Output — The Safe Way

```python
from openai import OpenAI
from pydantic import BaseModel

class InvoiceFields(BaseModel):
    client_name: str
    amount: float
    currency: str
    service: str

client = OpenAI()
resp = client.beta.chat.completions.parse(
    model="gpt-4o-mini",
    messages=[{"role": "user", "content": raw_text}],
    response_format=InvoiceFields,  # guaranteed valid JSON schema
)
fields = resp.choices[0].message.parsed   # typed Python object
```

No more regex on model output. No more JSON parse errors.  
The API guarantees the response matches the schema or raises an error.

---

## Model Selection Decision Tree

```
Does the task require:
  ├── Complex multi-step reasoning? → gpt-4o or claude-sonnet-4-6
  ├── Just formatting/extraction?   → gpt-4o-mini (10× cheaper)
  ├── Ultra-fast response (<1s)?    → Groq + llama-3.3-70b
  ├── Text similarity / search?     → text-embedding-3-small (no generation)
  └── Local / no API key?           → all-MiniLM-L6-v2 (sentence-transformers)
```

---

## The Learning Loop as an LLM System

Our `scripts/learning_loop.py` is itself an LLM-powered system:

1. **Audit log** = structured observation of a completed request
2. **Pattern detection** = counting token (skill) co-occurrence across requests
3. **Threshold promotion** = rule-based: skills used N times → hook promoted
4. **Risk scoring** = actuarial formula, not LLM (deterministic, auditable)

Karpathy's lesson: *"Use the simplest tool that works."*  
We use LLMs where language understanding matters.  
We use rules where determinism matters (pricing, risk, compliance).

---

## Further Reading (Karpathy Curriculum)

| Resource | What you learn |
|----------|----------------|
| [*makemore*](https://github.com/karpathy/makemore) | Bigram → MLP → RNN → transformer from scratch |
| [*nanoGPT*](https://github.com/karpathy/nanoGPT) | Full GPT-2 training in 300 lines |
| [*minbpe*](https://github.com/karpathy/minbpe) | BPE tokenizer from scratch |
| [*Let's build GPT*](https://www.youtube.com/watch?v=kCc8FmEb1nY) | 2hr YouTube walkthrough (best intro ever made) |
| [*Intro to LLMs*](https://www.youtube.com/watch?v=zjkBMFhNj_g) | 1hr high-level talk, covers RLHF + jailbreaks |
| Attention Is All You Need (2017) | Original transformer paper — 13 pages |
| GPT-2 paper (2019) | Language models are few-shot learners |

---

*End of LLM Wiki — AI Studio Accademia Milano — 2026-05-23*
