# Deliverable 002 — PDF Generator + Email Sender

> Purpose: Generates a PDF (`funziona.pdf`) and sends it via Gmail using OAuth2.
> Owner Agent: Chiara
> Status: active

## Credentials Required

| Credential | Required | Type |
|---|---|---|
| `credentials.json` | **Yes** | Google OAuth2 client secret file |
| `token.json` | Auto-generated on first run | OAuth2 access + refresh token |

> ⚠️ Never commit `credentials.json` or `token.json` to git. Both are in `.gitignore`.

---

## Setup

### 1. Enable Gmail API in Google Cloud

1. Go to [console.cloud.google.com](https://console.cloud.google.com)
2. Create a new project (or use an existing one)
3. **APIs & Services → Enable APIs** → search for **Gmail API** → Enable
4. **APIs & Services → Credentials → Create Credentials → OAuth 2.0 Client ID**
   - Application type: **Desktop app**
   - Name: anything (e.g. `AI Studio PDF Sender`)
5. Click **Download JSON** → save as `credentials.json` in this folder

### 2. Add your Gmail address as a test user

1. **APIs & Services → OAuth consent screen → Test users**
2. Add the Gmail address you want to send from

### 3. Install dependencies

```bash
pip install -r requirements.txt
```

### 4. Run

```bash
python main.py
```

On first run a browser window opens — sign in with your Google account and grant permission. This creates `token.json` locally. Subsequent runs use the saved token.

---

## What it produces

- `funziona.pdf` — A4 PDF with "Funziona!" in Helvetica Bold 48pt, centred
- Sends that PDF to `stekkino@hotmail.it` via your Gmail account

Change the recipient in `main.py` before running.

---

## Troubleshooting

| Error | Fix |
|---|---|
| `credentials.json not found` | Download it from Google Cloud Console (step 1 above) |
| `Token has been expired or revoked` | Delete `token.json` and run again to re-authenticate |
| `Access blocked: app not verified` | Add your Gmail as a test user (step 2 above) |
