# Credentials Registry — AI Studio Accademia Milano

Central reference for every credential used in this project.
Copy `.env.example` → `.env`, fill values in as you obtain them.
This file is committed. `.env` is never committed (gitignored).

---

## Quick Reference — Which deliverable needs what

| Credential | D002 | D003 | D005 | D007 | D008 | D009 | D010 | Pipeline | Research |
|---|:---:|:---:|:---:|:---:|:---:|:---:|:---:|:---:|:---:|
| ANTHROPIC_API_KEY | | | ✓ | | | ✓ | ✓ | ✓ | |
| OPENAI_API_KEY | | | ✓ | ✓ | | | | | |
| GITHUB_TOKEN | | | | | | ✓ | | ✓ | ✓ |
| GOOGLE_CREDENTIALS_JSON | ✓ | ✓ | | ✓ | | | | | |
| TELEGRAM_BOT_TOKEN | | | | ✓ | | | ✓ | ✓ | |
| TELEGRAM_CHANNEL_ID | | | | | | | ✓ | ✓ | |
| TWITTER_* (4 vars) | | | | | | | ✓ | ✓ | |
| DISCORD_WEBHOOK_URL | | | | | | | ✓ | ✓ | |
| REDDIT_* (4 vars) | | | | | | | ✓ | | |
| META_ACCESS_TOKEN | | | | ✓ | | | | | |
| TWILIO_AUTH_TOKEN | | | | ✓ | | | | | |
| ALPACA_API_KEY / SECRET | | | | | ✓ | | | | |
| MS_CLIENT_ID | | | | ✓ | | | | | |
| APPLE_APP_PASSWORD | | | | ✓ | | | | | |

---

## ANTHROPIC

**Vars:** `ANTHROPIC_API_KEY`  
**Priority:** P0 — blocks most deliverables

### How to get
1. Go to [console.anthropic.com](https://console.anthropic.com)
2. Sign in (or create account)
3. Left sidebar → **API Keys** → **Create Key**
4. Copy the key (shown once) → paste into `.env`

**Cost:** pay-per-token. Claude Sonnet 4.6 ≈ $3/$15 per 1M input/output tokens.

---

## OPENAI

**Vars:** `OPENAI_API_KEY`  
**Priority:** P1 — needed for RAG scripts, D007 event parser, D005 chatbot

### How to get
1. Go to [platform.openai.com](https://platform.openai.com)
2. Top-right → **API Keys** → **Create new secret key**
3. Copy key → paste into `.env`

**Cost:** text-embedding-3-small ≈ $0.02/1M tokens. GPT-4o-mini for RAG chat ≈ $0.15/$0.60.

---

## GITHUB

**Vars:** `GITHUB_TOKEN`, `RESEARCH_GITHUB_TOKEN`  
**Priority:** P1 — optional but recommended (60 → 5000 req/h)

### How to get
1. GitHub → **Settings** → **Developer settings** → **Personal access tokens** → **Tokens (classic)**
2. **Generate new token** → check scope: `public_repo`
3. Copy token → paste into `.env` for both vars (can be the same token)

---

## GMAIL / GOOGLE (OAuth)

**Vars:** `GOOGLE_CREDENTIALS_JSON`, `GOOGLE_TOKEN_JSON`  
**Priority:** P1 — needed for D002, D003 (email delivery), D007 (Google Calendar)  
**Note:** these point to local file paths, not the key values themselves.

### How to get credentials.json
1. Go to [console.cloud.google.com](https://console.cloud.google.com)
2. Create or select a project
3. **APIs & Services** → **Library** → enable **Gmail API** and **Google Calendar API**
4. **APIs & Services** → **Credentials** → **Create Credentials** → **OAuth 2.0 Client ID**
5. Application type: **Desktop app** → Create
6. Download JSON → save as `credentials.json` in repo root (gitignored)
7. First run will open browser for OAuth consent → generates `google_token.json` locally

**Cost:** free tier covers normal usage.

---

## TELEGRAM

**Vars:** `TELEGRAM_BOT_TOKEN`, `TELEGRAM_CHANNEL_ID`  
**Priority:** P1 — needed for D007 (calendar bot) and the digital presence pipeline

### How to get TELEGRAM_BOT_TOKEN
1. Open Telegram → search **@BotFather**
2. Send `/newbot`
3. Follow prompts (name + username ending in `bot`)
4. BotFather replies with token like `1234567890:ABCdef...`
5. Paste into `.env`

### How to get TELEGRAM_CHANNEL_ID
- **Public channel:** use `@your_channel_username` (e.g. `@aistudiomilano`)
- **Private channel:** add your bot as admin, send a message, then call:
  `https://api.telegram.org/bot<TOKEN>/getUpdates` — look for `"chat":{"id": -1001234567890}`
- Paste into `.env`

**Cost:** free.

---

## TWITTER / X

**Vars:** `TWITTER_API_KEY`, `TWITTER_API_SECRET`, `TWITTER_ACCESS_TOKEN`, `TWITTER_ACCESS_SECRET`  
**Priority:** P2 — needed only if auto-posting to Twitter/X

### How to get
1. Go to [developer.twitter.com](https://developer.twitter.com) → **Developer Portal**
2. Create a project + app (Free tier works for posting)
3. App → **Keys and Tokens**:
   - **API Key and Secret** → copy both
   - **Access Token and Secret** → Generate → copy both
4. Paste all four into `.env`

**Note:** Free tier allows 1500 tweets/month. Enough for weekly posts.

---

## DISCORD

**Vars:** `DISCORD_WEBHOOK_URL`  
**Priority:** P2 — needed only if auto-posting to Discord

### How to get
1. Open Discord → go to your server/channel
2. **Channel Settings** (gear icon) → **Integrations** → **Webhooks** → **New Webhook**
3. Name it, assign to channel → **Copy Webhook URL**
4. Paste into `.env`

**Cost:** free.

---

## REDDIT

**Vars:** `REDDIT_CLIENT_ID`, `REDDIT_CLIENT_SECRET`, `REDDIT_USERNAME`, `REDDIT_PASSWORD`  
**Priority:** P3 — optional publishing channel

### How to get
1. Go to [reddit.com/prefs/apps](https://www.reddit.com/prefs/apps)
2. Scroll down → **Create App**
3. Type: **script** | Name: AIStudioMilano | redirect uri: `http://localhost:8080`
4. After creation: **client_id** is under the app name, **client_secret** is labeled "secret"
5. Use your normal Reddit username and password for the remaining two vars

---

## META / WHATSAPP

**Vars:** `META_ACCESS_TOKEN`, `META_VERIFY_TOKEN`  
**Priority:** P2 — needed for D007 WhatsApp calendar bot

### How to get META_ACCESS_TOKEN
1. Go to [developers.facebook.com](https://developers.facebook.com)
2. **My Apps** → Create App → Business type
3. Add **WhatsApp** product → **API Setup**
4. Copy the temporary access token (valid 24h) or generate a permanent System User token via Business Manager
5. Set `META_VERIFY_TOKEN` to any string you choose (e.g. `aistudio_verify`) — must match exactly what you enter in the Meta webhook config

---

## TWILIO

**Vars:** `TWILIO_ACCOUNT_SID`, `TWILIO_AUTH_TOKEN`  
**Priority:** P2 — alternative WhatsApp channel via Twilio sandbox

### How to get
1. Go to [console.twilio.com](https://console.twilio.com)
2. Dashboard → **Account Info** → copy **Account SID** and **Auth Token**
3. Activate WhatsApp sandbox: **Messaging** → **Try it out** → **Send a WhatsApp message**

**Cost:** Twilio sandbox is free. Production: ≈$0.005/message.

---

## ALPACA (Paper Trading)

**Vars:** `ALPACA_API_KEY`, `ALPACA_SECRET_KEY`  
**Priority:** P2 — needed for D008 algo trading bot

### How to get
1. Go to [alpaca.markets](https://alpaca.markets) → **Sign Up** (free)
2. Dashboard → toggle to **Paper Trading**
3. **Paper Trading API Keys** → **Regenerate** → copy both keys
4. Paste into `.env`

**Important:** D008 uses paper trading only. Never use live trading keys with it.  
**Cost:** free (paper trading).

---

## MICROSOFT / OUTLOOK

**Vars:** `MS_CLIENT_ID`, `MS_TENANT_ID`  
**Priority:** P2 — needed for D007 Outlook Calendar sync

### How to get
1. Go to [portal.azure.com](https://portal.azure.com)
2. **Azure Active Directory** → **App registrations** → **New registration**
3. Name: AIStudioMilano | Supported account types: Personal Microsoft accounts | Redirect: `http://localhost`
4. After creation: copy **Application (client) ID** → `MS_CLIENT_ID`
5. For personal accounts: `MS_TENANT_ID=common`
6. **API permissions** → Add → Microsoft Graph → `Calendars.ReadWrite`

---

## APPLE ICLOUD

**Vars:** `APPLE_ICLOUD_USERNAME`, `APPLE_APP_PASSWORD`  
**Priority:** P2 — needed for D007 Apple Calendar sync  
**CRITICAL:** app-specific password only — never your main Apple ID password

### How to get
1. Go to [appleid.apple.com](https://appleid.apple.com)
2. Sign In → **Sign-In & Security** → **App-Specific Passwords**
3. Click **+** → label it "AIStudio" → Apple generates a 16-char password like `xxxx-xxxx-xxxx-xxxx`
4. Paste into `.env` — this is shown once only

---

## GitHub Actions Secrets

For the automated pipeline (`digital_presence.yml`), add these same vars as **repository secrets**:

1. GitHub repo → **Settings** → **Secrets and variables** → **Actions** → **New repository secret**
2. Add each var from `.env` that the workflow uses

Minimum set to activate the weekly LinkedIn post pipeline:
- `ANTHROPIC_API_KEY`
- `TELEGRAM_BOT_TOKEN` + `TELEGRAM_CHANNEL_ID`

---

## Status Tracker

Update this table as you obtain credentials:

| Credential | Status | Date obtained |
|---|---|---|
| ANTHROPIC_API_KEY | ☐ pending | |
| OPENAI_API_KEY | ☐ pending | |
| GITHUB_TOKEN | ☐ pending | |
| GOOGLE_CREDENTIALS_JSON | ☐ pending | |
| TELEGRAM_BOT_TOKEN | ☐ pending | |
| TELEGRAM_CHANNEL_ID | ☐ pending | |
| TWITTER_API_KEY | ☐ pending | |
| TWITTER_API_SECRET | ☐ pending | |
| TWITTER_ACCESS_TOKEN | ☐ pending | |
| TWITTER_ACCESS_SECRET | ☐ pending | |
| DISCORD_WEBHOOK_URL | ☐ pending | |
| REDDIT_CLIENT_ID | ☐ pending | |
| REDDIT_CLIENT_SECRET | ☐ pending | |
| ALPACA_API_KEY | ☐ pending | |
| ALPACA_SECRET_KEY | ☐ pending | |
| META_ACCESS_TOKEN | ☐ pending | |
| TWILIO_AUTH_TOKEN | ☐ pending | |
| MS_CLIENT_ID | ☐ pending | |
| APPLE_APP_PASSWORD | ☐ pending | |
