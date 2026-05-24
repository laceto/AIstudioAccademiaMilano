---
title: AI Studio Dispenser
emoji: 🤖
colorFrom: indigo
colorTo: blue
sdk: docker
app_port: 8501
pinned: false
license: mit
short_description: QR-driven order form for the AI Studio physical dispenser
---

# Dispenser input v1

A Streamlit form behind a QR code that lives on a physical AI dispenser. Users scan, pick a product, describe what they need, pay, and get the deliverable on WhatsApp / Telegram.

## v1 scope (what's built)

- **Payment**: Stripe Checkout (clean API, drop-in `PaymentProvider` ABC — `SatispayProvider` + `PayPalProvider` are stubbed)
- **Input**: guided wizard from `config/global_settings.json` priced catalog (`CatalogClassifier`); free-text `LLMClassifier` is stubbed for v2
- **Delivery**: WhatsApp (Twilio) + Telegram (Bot API), user picks one or both
- **Queue**: file-backed JSON queue (`request_queue.py`) — drop-in replaceable with SQLite/Redis later
- **Operator CLI** (`deliver.py`): list / show / notify-admin / send-and-mark-done
- **Hosting**: HF Spaces frontmatter + Dockerfile (Cloud Run / Render compatible — same shape as deliverable 013)

## URL contract

The QR sticker on each dispenser encodes:

```
https://<host>/?d=<dispenser-id>
```

`<dispenser-id>` ends up in every request's metadata (Stripe + queue + audit) so we can attribute requests to physical units later.

## Architecture

```
User phone (QR scan)
   │
   ▼
Streamlit (main.py)
   │ 1. pick product (CatalogClassifier)
   │ 2. enter details + recipient
   │ 3. Stripe Checkout redirect
   ▼
Stripe → callback ?session_id=…
   │
   ▼
Streamlit verifies payment → request_queue.enqueue()
   │
   ▼
Operator (Luigi) sees the request
  - either pinged via `python deliver.py notify <id>` (Telegram)
  - or polls `python deliver.py list`
   │
   ▼
Operator builds the deliverable (the 6-agent pipeline)
   │
   ▼
`python deliver.py send <id> <output-file>`
   │
   ▼
WhatsAppDelivery + TelegramDelivery → user gets it
```

## Local run

```bash
cp .streamlit/secrets.toml.example .streamlit/secrets.toml
# edit secrets.toml with real keys

pip install -r requirements.txt
streamlit run main.py
```

Without any keys configured, the form renders and validates inputs but stops before the payment step (it shows the would-be queue payload as JSON).

## Operator CLI

```bash
python deliver.py list                       # show pending paid requests
python deliver.py show 7c3f9a12              # full record (prefix match OK)
python deliver.py notify                     # ping admin via Telegram about all pending
python deliver.py notify 7c3f9a12            # ping about one specific request
python deliver.py send 7c3f9a12 out.md       # deliver `out.md` to the user's channels
                                             # and mark the request done
```

## Deploy

Same Docker shape as deliverable 013 — works on:

- **HF Spaces (Docker SDK)**: push this folder as the Space root; the frontmatter at the top of this README is the Space config. Add Stripe / Twilio / Telegram keys in *Settings → Variables and secrets*.
- **Cloud Run**: `gcloud run deploy dispenser --source . --memory 512Mi --session-affinity --set-secrets STRIPE_SECRET_KEY=stripe-key:latest,TWILIO_ACCOUNT_SID=twilio-sid:latest,…`
- **Render / Railway / Fly.io**: any Docker host.

## Roadmap

| Item | When |
|---|---|
| Free-text request → LLM classifier (`LLMClassifier`) with Marco escalation on low confidence | v2 |
| Satispay payment provider | v2 |
| PayPal payment provider | v2 |
| Migrate queue from JSON file to SQLite (single-process) → Redis/Cloud Tasks (multi-process) | when volume > 1 req/sec |
| Per-product required-fields wizard (from `process/intent_registry.yaml`) | when guided picker is too coarse |
| LLM intent classification before payment (catch ambiguity early) | v2 |

## TODOs / credentials to obtain before going live

- [ ] Stripe account + restricted-keys API key (`sk_…`)
- [ ] Twilio account + WhatsApp sender (sandbox for dev, approved sender for prod)
- [ ] Telegram bot via @BotFather + `TELEGRAM_BOT_TOKEN`
- [ ] Luigi's Telegram chat_id (start the bot, then check `https://api.telegram.org/bot<token>/getUpdates`)
- [ ] Public HTTPS URL (HF Spaces / Cloud Run) before printing QR stickers
- [ ] Italian VAT / Stripe Tax setup (consult accountant)

## File layout

```
main.py                  # Streamlit form + payment redirect handler
deliver.py               # Operator CLI
request_queue.py         # JSON-file queue
payments/
  base.py                # PaymentProvider ABC
  stripe_provider.py     # active in v1
  satispay_provider.py   # v2 stub
  paypal_provider.py     # v2 stub
classifiers/
  base.py                # RequestClassifier ABC
  catalog_classifier.py  # active in v1 (dropdown)
  llm_classifier.py      # v2 stub (free-text → priced product via LLM)
delivery/
  base.py                # DeliveryChannel ABC
  whatsapp.py            # Twilio
  telegram.py            # Bot API
requirements.txt
Dockerfile
.streamlit/secrets.toml.example
```
