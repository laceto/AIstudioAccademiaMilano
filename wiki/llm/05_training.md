# 05 — Training & Alignment

## Stage 1: Pretraining

Objective: predict the next token. That's it.

```python
logits  = model(tokens)           # (B, T, vocab_size)
targets = tokens[:, 1:]           # shift by 1
loss    = F.cross_entropy(logits[:, :-1].reshape(-1, vocab_size), targets.reshape(-1))
```

Run over ~10-15 trillion tokens of internet text. Cost for GPT-4: ~$100M. LLaMA 3 70B: ~$2M.

## Stage 2: SFT (Supervised Fine-Tuning)

Teaches `User → Assistant` format using thousands of human-written examples.  
Base model → instruction-following model. LLaMA 3 base → LLaMA 3 Instruct.

## Stage 3: Alignment — Three Approaches

### RLHF + PPO (original, OpenAI GPT-4)
1. Show humans two responses → pick better one → train reward model
2. PPO: maximise `reward − β × KL(policy, ref_policy)`

Complex. Needs a separate reward model. Sensitive to reward hacking.

### DPO — Direct Preference Optimization (simpler, widely adopted 2024)

No reward model needed. Directly fine-tune on preference pairs `(chosen, rejected)`.

```python
# HuggingFace TRL — one trainer call
from trl import DPOTrainer, DPOConfig

trainer = DPOTrainer(
    model=model,
    ref_model=ref_model,
    args=DPOConfig(output_dir="dpo-output", beta=0.1),
    train_dataset=dataset,   # {"prompt", "chosen", "rejected"}
    tokenizer=tokenizer,
)
trainer.train()
```

Used by: Mistral, Phi-3, Gemma 2, most open-source RLHF pipelines.  
`beta=0.1` is standard; lower = closer to reference model.

### GRPO — Group Relative Policy Optimization (DeepSeek-R1, 2025)

No reference model, no reward model. Score a group of sampled responses, use relative ranking as signal.

```
Sample k=8 responses per prompt → score each → normalize → PPO-style update
Reward signal: verifiable (math answer correct? code compiles?)
```

Key insight: for tasks with ground-truth answers, you don't need human preferences. The answer IS the reward.  
This is how DeepSeek-R1 learned to reason — chain-of-thought emerged from GRPO on math/code, not from human feedback.

### Constitutional AI — Anthropic variant

RLAIF: AI evaluates AI using a written "Constitution" of principles. Claude's constitution specifies ~58 rules (be helpful, harmless, honest). No human labellers needed at scale.

## Fine-Tuning at the Studio

**RAG vs Fine-tuning decision:**

| Scenario | Use RAG | Fine-tune |
|----------|---------|----------|
| Knowledge changes frequently | ✅ | ❌ |
| Style / tone / format | ❌ | ✅ |
| Fast iteration | ✅ | ❌ |
| No GPU available | ✅ | ❌ |
| Consistent structured output | ❌ | ✅ |

**Studio default: RAG first.**

### LoRA — Parameter-Efficient Fine-Tuning

Don't update all weights. Inject small trainable matrices A, B alongside frozen weights.

```python
# W_new = W_frozen + A @ B    (A: d×r, B: r×d, r << d)
# Only train A and B — typically 0.1% of total params

from peft import LoraConfig, get_peft_model
config = LoraConfig(r=8, lora_alpha=16, target_modules=["q_proj", "v_proj"])
model = get_peft_model(base_model, config)
model.print_trainable_parameters()  # e.g. "0.08% of 8B params"
```

LoRA + DPO on a 7B model fits on a single A100 (40GB). Typical cost: ~$20 on Lambda/RunPod.

### HuggingFace TRL for the Studio

```bash
pip install trl peft transformers datasets
```

```python
from trl import SFTTrainer, SFTConfig
from datasets import load_dataset

dataset = load_dataset("json", data_files="data/studio_examples.jsonl")["train"]
trainer = SFTTrainer(
    model="meta-llama/Meta-Llama-3-8B",
    args=SFTConfig(output_dir="fine-tuned", num_train_epochs=3),
    train_dataset=dataset,
)
trainer.train()
trainer.model.push_to_hub("laceto/studio-llama3-8b")  # needs HF_TOKEN
```

*Next: [06 — Inference](06_inference.md)*
