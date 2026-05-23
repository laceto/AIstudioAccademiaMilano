# Deliverable 007 — AI Calendar Sync + Multi-Channel Bot

> Purpose: Syncs events across Google Calendar, Outlook, and Apple Calendar via a Streamlit UI, Telegram bot, or WhatsApp bot.
> Owner Agent: Chiara
> Status: active

## Credentials Overview

This deliverable integrates multiple services. You only need credentials for the ones you actually use.

| Service | Credential | Required for |
|---|---|---|
| OpenAI | `OPENAI_API_KEY` | AI scheduling suggestions |
| Google Calendar | `GOOGLE_CREDENTIALS_JSON`, `GOOGLE_TOKEN_JSON` | Google Calendar sync |
| Microsoft / Outlook | `MS_CLIENT_ID`, `MS_TENANT_ID` or `OUTLOOK_ACCESS_TOKEN` | Outlook sync |
| Apple iCloud | `APPLE_ICLOUD_USERNAME`, `APPLE_APP_PASSWORD` | Apple Calendar sync |
| Telegram | `TELEGRAM_BOT_TOKEN` | Telegram bot interface |
| Twilio (WhatsApp) | `TWILIO_ACCOUNT_SID`, `TWILIO_AUTH_TOKEN`, `TWILIO_WHATSAPP_FROM` | WhatsApp via Twilio |
| Meta WhatsApp Cloud | `META_PHONE_NUMBER_ID`, `META_ACCESS_TOKEN`, `META_VERIFY_TOKEN` | WhatsApp via Meta API |

---

## Setup by Service

### OpenAI
1. Get an API key at [platform.openai.com/api-keys](https://platform.openai.com/api-keys)
2. Set: `export OPENAI_API_KEY=sk-...`

---

### Google Calendar
1. [console.cloud.google.com](https://console.cloud.google.com) → Enable **Google Calendar API**
2. Create OAuth 2.0 Client ID (Desktop app) → download `credentials.json`
3. Set:
   ```bash
   export GOOGLE_CREDENTIALS_JSON=$(cat credentials.json)
   ```
4. On first run `token.json` is generated automatically.
   ```bash
   export GOOGLE_TOKEN_JSON=$(cat token.json)
   ```
> ⚠️ Never commit `credentials.json` or `token.json`. They are in `.gitignore`.

---

### Microsoft / Outlook
1. [portal.azure.com](https://portal.azure.com) → App registrations → New registration
2. Add `Calendars.ReadWrite` permission under Microsoft Graph
3. Set:
   ```bash
   export MS_CLIENT_ID=your_client_id
   export MS_TENANT_ID=your_tenant_id
   ```
   Or use a short-lived access token:
   ```bash
   export OUTLOOK_ACCESS_TOKEN=your_token
   ```

---

### Apple iCloud
1. Go to [appleid.apple.com](https://appleid.apple.com) → Sign-In and Security → **App-Specific Passwords**
2. Generate a new app-specific password (e.g. `AI Studio Calendar`)
3. Set:
   ```bash
   export APPLE_ICLOUD_USERNAME=your@icloud.com
   export APPLE_APP_PASSWORD=xxxx-xxxx-xxxx-xxxx
   ```
> ⚠️ Use **only** the app-specific password. Never use your main Apple ID password.

---

### Telegram Bot
1. Open Telegram → message **@BotFather** → `/newbot`
2. Follow the prompts → copy the token
3. Set:
   ```bash
   export TELEGRAM_BOT_TOKEN=123456789:ABCdef...
   ```

---

### WhatsApp via Twilio
1. Sign up at [twilio.com](https://twilio.com) → Messaging → WhatsApp Sandbox
2. Copy Account SID and Auth Token from the Twilio console
3. Set:
   ```bash
   export TWILIO_ACCOUNT_SID=ACxxxx
   export TWILIO_AUTH_TOKEN=your_token
   export TWILIO_WHATSAPP_FROM=whatsapp:+14155238886
   ```
> ⚠️ Twilio webhook uses HMAC-SHA1 signature validation — active in production by default.

---

### WhatsApp via Meta Cloud API
1. [developers.facebook.com](https://developers.facebook.com) → Create App → WhatsApp Business
2. Set:
   ```bash
   export META_PHONE_NUMBER_ID=your_phone_number_id
   export META_ACCESS_TOKEN=your_access_token
   export META_VERIFY_TOKEN=your_custom_verify_token
   ```

---

## Run

### Streamlit dashboard
```bash
pip install -r requirements.txt
streamlit run setup_app.py
```
Credentials can also be entered via the Streamlit sidebar instead of env vars.

### Telegram bot
```bash
python bot_telegram.py
```

### WhatsApp bot
```bash
python bot_whatsapp.py
```

---

## Minimum viable setup

To get started with the least friction:
1. Set `OPENAI_API_KEY`
2. Set up Google Calendar credentials
3. Run `streamlit run setup_app.py`

Add Telegram, WhatsApp, Outlook, and Apple only when needed.
