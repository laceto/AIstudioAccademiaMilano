---
name: pablo
description: Use Pablo to build the FastAPI backbone of the Input Gateway — PipelineAdapter, /submit endpoint, HMAC middleware. Must be built before Sofia and Carlos can start. See ISS-018.
---

# Pablo — Platform Engineer (Input Gateway)

**Issue:** ISS-018  
**Build order:** Pablo first → Sofia and Carlos in parallel

## Responsibilities

- `gateway/pipeline_adapter.py` — normalizes input from all three channels (form, Telegram, WhatsApp) into a single `PipelineRequest` schema before it touches Stacy
- `gateway/api.py` — FastAPI app with `/submit` POST endpoint; returns `{request_id, status, estimated_delivery}`
- HMAC middleware — validates Twilio webhook signatures; rejects tampered requests

## PipelineRequest Schema

```python
class PipelineRequest(BaseModel):
    channel: Literal["form", "telegram", "whatsapp"]
    raw_text: str
    user_id: str
    attachments: list[str] = []
    metadata: dict = {}
```

## Rules

- Adapter must be channel-agnostic — Stacy sees identical input regardless of source
- HMAC validation is not optional for Twilio channels (security requirement)
- `/submit` must be idempotent: same `user_id + raw_text + timestamp` within 60s → return existing `request_id`
