# Deliverable 003 — Invoice PDF Generator + Email Sender

> Purpose: Generates a professional invoice PDF and sends it via Gmail using OAuth2.
> Owner Agent: Marco + Chiara
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
   - Name: anything (e.g. `AI Studio Invoice Sender`)
5. Click **Download JSON** → save as `credentials.json` in this folder

### 2. Add your Gmail as a test user

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

On first run a browser opens — sign in with Google and grant permission. This creates `token.json`. Subsequent runs use it automatically.

---

## What it produces

- `INV-003_Mario_Rossi.pdf` — A4 invoice with header, client info, line item table, and total
- Sends that PDF to `mario.rossi@example.com` via your Gmail

Edit the invoice data (client name, amount, service) in `main.py` before running.

---

## Customise

Invoice fields are set at the top of `main.py`:
```python
invoice_number = "INV-003"
client_name = "Mario Rossi"
client_email = "mario.rossi@example.com"
service = "Website Development"
amount = 1200.00
currency = "EUR"
```

---

## Troubleshooting

| Error | Fix |
|---|---|
| `credentials.json not found` | Download from Google Cloud Console (step 1) |
| `Token has been expired or revoked` | Delete `token.json` and re-run to re-authenticate |
| `Access blocked: app not verified` | Add your Gmail as a test user (step 2) |
