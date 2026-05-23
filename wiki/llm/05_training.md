# 05 — Training & Alignment

> "Pretraining is compression. RLHF is alignment. Fine-tuning is adaptation."

---

## Stage 1: Pretraining (The Foundation)

**Objective:** predict the next token.

```python
# Loss for one position
logits = model(tokens)          # (B, T, vocab_size)
targets = tokens[:, 1:]        # shift by 1 — next token is the target
loss = F.cross_entropy(logits[:, :-1].reshape(-1, vocab_size),
                        targets.reshape(-1))
```

Cross-entropy loss on next-token prediction over ~10 trillion tokens of internet text.  
Nothing else. No labels. No human feedback. Just compression.

**What emerges from this simple objective:**
- Grammar and syntax (forced by prediction)
- World knowledge (learned from Wikipedia, books, code)
- Reasoning patterns (chain-of-thought appears at scale)
- Coding ability (GitHub is in the training data)

**Cost:** GPT-4 training ≈ $100M+ in compute. GPT-2 (117M): ~$50k.

---

## Stage 2: Supervised Fine-Tuning (SFT)

The pretrained model completes text — it doesn't follow instructions.  
SFT teaches it to follow the `User → Assistant` format.

```
Training examples:
[User]: Write a haiku about machine learning.
[Assistant]: Patterns emerge slow, / Weights adjust through gradient, / Loss falls toward zero.

[User]: What is the capital of Italy?
[Assistant]: Rome.
```

Thousands of high-quality human-written examples.  
Same loss function, restricted to the assistant tokens only.

---

## Stage 3: RLHF — Reinforcement Learning from Human Feedback

Karpathy's explanation: *"The model learns to produce outputs that humans prefer."*

### Step A: Train a Reward Model

```
For each prompt, show humans two model responses:
  Response A: "The capital of Italy is Rome."
  Response B: "Italy has many cities. Rome is notable among them."

Human picks A (more direct).
Reward model learns: prefer_A > prefer_B.
```

### Step B: PPO Optimization

Use the reward model as a signal to fine-tune the LLM:  
→ Increase probability of responses the reward model rates highly.  
→ KL-divergence penalty prevents the model from drifting too far from SFT baseline.

```python
# Simplified PPO objective
reward = reward_model(response)           # scalar
kl_penalty = kl_divergence(policy, ref_policy)
loss = -(reward - beta * kl_penalty)     # beta ~ 0.1
```

### Step C: RLAIF / Constitutional AI (Anthropic)

Replace human labellers with another AI (Claude evaluates Claude).  
Scale feedback cheaply. Encode values as a written "Constitution".

---

## Stage 4: Fine-Tuning for the Studio

We do *not* run RLHF — that's OpenAI's job.  
What we can do:

### LoRA (Low-Rank Adaptation)

```python
# Instead of updating all 7B parameters:
# W_new = W_original + ΔW,  where ΔW = A @ B
# A: (d_model, r), B: (r, d_model), r << d_model

# Only A and B are trained — <1% of parameters
from peft import get_peft_model, LoraConfig

config = LoraConfig(r=16, lora_alpha=32, target_modules=["q_proj", "v_proj"])
model  = get_peft_model(base_model, config)
# Trainable params: ~0.5% of total
```

### When to fine-tune vs RAG?

| Scenario | Use RAG | Use Fine-tuning |
|----------|---------|------------------|
| Knowledge changes frequently | ✅ | ❌ |
| Need citations/sources | ✅ | ❌ |
| Style / tone / format | ❌ | ✅ |
| Domain-specific reasoning | ❌ | ✅ |
| Fast iteration | ✅ | ❌ |

**Studio default:** RAG first. Fine-tune only if RAG isn't enough.

---

## Loss Curves — Reading the Compass

```
Training loss:  ↘ always falling  (model memorises training data)
Validation loss: ↘ then → or ↗
                         ^
                         Overfitting starts here
```

```python
# Perfect loss for next-token prediction on random data:
# loss = -log(1/vocab_size) = log(50257) ≈ 10.8

# GPT-2 small after pretraining: ≈ 2.85
# GPT-3 175B:                     ≈ 1.73
# GPT-4 (estimated):              ≈ 1.2
```

---

*Next: [06 — Inference & Sampling](06_inference.md)*
