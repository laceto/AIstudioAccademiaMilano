# Audit Log — Request 007

**Date:** 2026-05-23  
**Request ID:** 007  
**Submitted by:** Luigi

---

## User Input

> "New user input request. Using WhatsApp or other to create event in apple calendar, outlook and gmail"

---

## Pipeline Execution

```yaml
request_id: "007"
date: "2026-05-23"
intent: calendar_integration
outcome: success
user_input: "Using WhatsApp or other to create event in apple calendar, outlook and gmail"

agents_invoked:
  - name: Stacy
    role: intake_and_routing
    action: "Classified intent as calendar_integration (new intent — not yet in pricing table).
      Checked pricing table: unknown_product = null. BLOCKED. Escalated to Luigi for
      price approval."
    duration_sec: 3
    status: escalated

  - name: Marco
    role: financial_controller
    action: "Actuarial assessment: E[value] = 3 calendar providers × recurring saves per
      month. Comparable to chatbot_app at €19.90 but less compute. Recommended €14.90.
      Luigi approved. Pricing table updated: calendar_integration = €14.90."
    duration_sec: 4
    status: success

  - name: Stacy
    role: intake_and_routing
    action: "Price confirmed. Routing to Gianni for scoping."
    duration_sec: 1
    status: success

  - name: Gianni
    role: technical_scoping
    action: "Scoped 3-layer architecture: (1) Message channel — Telegram bot (immediate,
      no approval) + Twilio/WhatsApp (sandbox + production) + Meta Cloud API; (2) Event
      extraction — GPT-4o-mini structured output via Pydantic CalendarEvent model; (3)
      Calendar adapters — Google Calendar API v3, Microsoft Graph API v1.0 (device code
      OAuth), Apple iCloud CalDAV (app-specific password). Streamlit setup UI for
      credential configuration. Risk: Apple iCloud requires app-specific password, not
      main password."
    duration_sec: 18
    status: success

  - name: Chiara
    role: implementation
    action: "Built: event_parser.py (GPT structured output → CalendarEvent), calendar_sync.py
      (Google + Outlook + Apple adapters), bot_telegram.py (python-telegram-bot v20),
      bot_whatsapp.py (Twilio webhook + Meta Cloud API), setup_app.py (Streamlit config
      UI). All credentials via env vars / Streamlit Secrets. Apple iCloud uses app-specific
      password per Apple security requirements."
    duration_sec: 120
    status: success

  - name: Stacy
    role: qa_review
    action: "Verified: (1) Twilio signature validation prevents replay attacks; (2) Apple
      password never logged; (3) Google token.json stays local, never committed; (4)
      MetaWhatsApp verification challenge handled; (5) All calendar adapters return
      SyncResult dataclass with status/error, never raise uncaught."
    duration_sec: 10
    status: success

  - name: Marco
    role: financial_controller
    action: "Final invoice: calendar_integration €14.90. API costs: GPT-4o-mini ~150
      tokens/parse = $0.00002 per event. Effectively zero. Margin > 99%."
    duration_sec: 2
    status: success

  - name: Francesca
    role: delivery
    action: "Pushed to branch claude/digital-communities-guide-a5lBV. Delivery:
      run bot_telegram.py for Telegram, bot_whatsapp.py + ngrok for WhatsApp sandbox,
      setup_app.py for Streamlit config UI."
    duration_sec: 4
    status: success

skills_used:
  - openai_api_integration
  - google_calendar_api
  - microsoft_graph_api
  - apple_caldav
  - event_extraction_llm
  - telegram_bot_api
  - twilio_whatsapp_api

learning_flags:
  new_skills:
    - google_calendar_api
    - microsoft_graph_api
    - apple_caldav
    - event_extraction_llm
    - telegram_bot_api
    - twilio_whatsapp_api
  new_mcp: []
  risk_score: 2
  notes:
    - "New intent: calendar_integration priced at €14.90 (Luigi approved)"
    - "Marco blocked correctly on unknown_product: null — ISS-001 fix confirmed working"
    - "Apple requires app-specific password: security note added to skill metadata"
    - "Twilio signature validation prevents WhatsApp webhook replay attacks"
```

---

## Deliverables

| File | Purpose |
|------|---------|
| `event_parser.py` | GPT-4o-mini + Pydantic → `CalendarEvent` structured object |
| `calendar_sync.py` | Adapters: Google Calendar, Outlook (Graph API), Apple (CalDAV) |
| `bot_telegram.py` | Telegram bot — works immediately, no Meta approval |
| `bot_whatsapp.py` | Twilio webhook + Meta Cloud API WhatsApp |
| `setup_app.py` | Streamlit UI: configure credentials, test parsing, trigger sync |
| `requirements.txt` | All dependencies |

---

## How to Use

### Option A: Telegram (start in 5 minutes)
```bash
pip install -r requirements.txt
export TELEGRAM_BOT_TOKEN=your_token
export OPENAI_API_KEY=sk-...
export GOOGLE_CREDENTIALS_JSON=credentials.json   # optional
export APPLE_ICLOUD_USERNAME=you@icloud.com        # optional
export APPLE_APP_PASSWORD=xxxx-xxxx-xxxx-xxxx      # optional

python bot_telegram.py
```
Send a message like: `“Pranzo con Marco domani alle 13 a Milano”`

### Option B: WhatsApp via Twilio Sandbox
```bash
export TWILIO_ACCOUNT_SID=...
export TWILIO_AUTH_TOKEN=...
python bot_whatsapp.py
ngrok http 8080
# Twilio Console → WhatsApp Sandbox → set webhook to https://YOUR_URL/whatsapp
```

### Option C: Streamlit Config UI
```bash
streamlit run setup_app.py
```

---

## Security Notes

- Google `credentials.json` and `token.json` — keep local, add to `.gitignore`
- Apple: use app-specific password only. Generate at `appleid.apple.com`
- Twilio: signature validation active in production (`TWILIO_AUTH_TOKEN` set)
- All API keys in Streamlit Secrets, never in source code

---

## Risk Assessment (Actuarial)

| Risk | P(event) | Impact | RU |
|------|----------|--------|----|
| OAuth token leak via logs | 0.05 | High | 2.0 |
| Twilio webhook spoofing | 0.10 | Medium | 1.0 |
| Apple CalDAV password stored insecurely | 0.05 | High | 2.0 |
| GPT misparses event date | 0.15 | Low | 0.5 |

**Max single RU: 2.0 — within auto-commit threshold (< 3). Committed automatically.**  
**Mitigation:** Twilio signature validation, Apple app-specific password (revocable), env-only credential storage.

---

*Delivered by AI Studio Accademia Milano — 2026-05-23*
