---
request_id: "—"
date: "2026-09-07"
intent: internal_infra_fix
product_type: internal_infra_fix
outcome: success
price: "€0.00"
invoice_id: "—"
agents_invoked:
  - name: Stacy
    role: intent_classifier
    action: Classified as internal_infra_fix (diagnostic + regression repair) — not unknown_product
    duration_sec: 2
    status: ok
  - name: Gianni
    role: technical_scoper
    action: Traced regression to token ownership conflict between pipeline bot and RAG webhook
    duration_sec: 8
    status: ok
  - name: Chiara
    role: implementer
    action: Added scripts/check_telegram.py; fixed register_telegram_webhook.py token; 14 new tests
    duration_sec: 90
    status: ok
  - name: Stacy QA
    role: output_validator
    action: QA passed — 218/218 collectable tests green, no token ever printed, no secrets committed
    duration_sec: 5
    status: ok
  - name: Marco
    role: transaction_manager
    action: Internal fix, €0.00 per Delivery ID Policy rule 5; no numbered ID consumed
    duration_sec: 2
    status: ok
skills_used:
  - telegram_bot_api
  - fastapi_webhook_routing
  - railway_deployment
delivery:
  method: github
  destination: scripts/check_telegram.py + scripts/rag/register_telegram_webhook.py
  confirmed: true
qa_result: pass
payment:
  amount: "€0.00"
  method: internal
  receipt_id: "—"
learning_flags:
  new_skills: []
  new_mcp: []
  risk_score: 2
  cost_overrun: false
  loss_development_flag: false
---

# Internal Infra Fix — Telegram Channel Regression

## Symptom

The "AI Studio Milano" bot answered correctly (pipeline ack + worker follow-up),
then went silent: a 2026-06-02 message got no reply at all. On 2026-06-08 the
same chat started producing RAG-style answers instead of pipeline replies.

## Root cause

`scripts/rag/register_telegram_webhook.py` (written 2026-05-29) registered the
RAG API webhook using `TELEGRAM_BOT_TOKEN` — the *pipeline* bot's token. Two
consequences:

1. Telegram refuses `getUpdates` while a webhook is set, so `gateway.bot_telegram`
   (`run_polling()`) was starved with a 409 and stopped receiving anything.
2. `scripts/rag/api_server.py:213` sends its replies with `TELEGRAM_RAG_BOT_TOKEN`,
   a *different* bot — so the pipeline bot's incoming updates were answered by the
   RAG service, as the wrong bot, or not at all when that var was unset.

The 2026-05-30 commits (`1915083`, `5a802cf`) split the RAG bot onto its own
token, but the registrar script was never updated to follow.

## Fix

- `register_telegram_webhook.py` now uses `TELEGRAM_RAG_BOT_TOKEN` and refuses to
  run if it matches `TELEGRAM_BOT_TOKEN` (guards the exact regression).
- New `scripts/check_telegram.py`: queries `getMe` + `getWebhookInfo` per bot and
  reports webhook/polling conflicts, queued updates, and delivery errors.
- `gateway/rag_bot_telegram.py` docstring corrected (`RAG_BOT_TOKEN` → `TELEGRAM_RAG_BOT_TOKEN`).

## Still open (needs Luigi — requires credentials/Railway access)

- Delete the stray webhook from the pipeline bot to restore polling.
- No Railway service exists for `gateway/Dockerfile` or `gateway/worker.py`; the
  root `railway.toml` builds `scripts/rag/Dockerfile` only. Until a gateway
  service is deployed, the 6-agent pipeline has no Telegram front door. (ISS-021)
