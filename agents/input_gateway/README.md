# Input Gateway Team

> Purpose: Build and own all user-facing input channels that feed the 6-agent pipeline.
> Status: active (introduced 2026-05-24)

## Why this team exists

The 6-agent pipeline has no real entry point. Today, Luigi talks to Claude Code directly — there is no frontend, no webhook, no API collecting requests from real users. The Input Gateway Team closes that gap.

## Three channels

| Channel | File | Owner |
|---------|------|-------|
| Streamlit form | `gateway/streamlit_app.py` | Sofia |
| FastAPI web form (POST endpoint) | `gateway/api.py` | Pablo |
| WhatsApp + Telegram bots | `gateway/bot_telegram.py`, `gateway/bot_whatsapp.py` | Carlos |

All three channels call one shared interface:

```python
# gateway/pipeline_adapter.py
class PipelineAdapter:
    def submit(self, text: str, channel: str, metadata: dict) -> dict:
        """Normalize input and hand to Stacy. Returns {job_id, status, result}."""
```

Stacy never sees which channel a request came from — just clean text + metadata.

## Build order

```
Pablo: PipelineAdapter + FastAPI  ──→  Sofia + Carlos (parallel)  ──→  Stacy QA  ──→  deploy
```

Pablo's `PipelineAdapter` is the prerequisite. Once it exists, Sofia and Carlos work in parallel against it.

## Composition

| Agent | Role | Primary lens |
|-------|------|------|
| Pablo | Platform Engineer | Does this hold under load and adversarial input? |
| Sofia | Frontend/UX | Does the user understand what's happening? |
| Carlos | Bot/Integration | Does the message survive lossy mobile networks and API rate limits? |

## Risk oversight

- **Technical Auditor** reviews Pablo's public endpoint before deploy (input validation, rate limiting, HMAC signature on webhooks)
- **Compliance Agent** checks WhatsApp and Telegram ToS on webhook data handling before Carlos ships

## Handoffs

- **Receives from**: Luigi (trigger) or any new delivery that requires a real user input channel
- **Sends to**: Stacy (normalized request) via `PipelineAdapter.submit()`
- **Logs to**: audit log under `agents_invoked` with role tag `input_gateway`

## Reference

- [`pablo.md`](./pablo.md) — Platform Engineer spec
- [`sofia.md`](./sofia.md) — Frontend/UX spec
- [`carlos.md`](./carlos.md) — Bot/Integration spec
- Issues: ISS-018 (Pablo), ISS-019 (Sofia), ISS-020 (Carlos), ISS-021 (deploy)
