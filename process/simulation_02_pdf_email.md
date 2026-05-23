# Simulation 02 — PDF Creation & Email Delivery

> **Purpose:** Trace a user text request through the full pipeline to verify the process handles document creation + email delivery end to end.

---

## User Input

```
I want a pdf with title only 'funziona' sent to stekkino@hotmail.it
from my gmail account
```

**Input type:** Text (typed at dispenser / chat interface)  
**Timestamp:** 2026-05-23 11:30

---

## Step 1 — Stacy captures and routes the input

**Agent:** Stacy (Input-Orchestrator)

| Field | Value |
|-------|-------|
| Input type detected | Text |
| Language | English |
| Voice-to-text needed | No |
| Intent extracted | Document creation + email delivery |
| Product type | PDF file |
| Key entities | Title: "funziona" · Recipient: stekkino@hotmail.it · Sender: user's Gmail |

**⚠️ Stacy flags a dependency before routing:**
> Sending from the user's Gmail requires OAuth 2.0 authorisation or a Gmail App Password.
> Stacy prompts the user at the dispenser:

```
ℹ️ Per inviare dalla tua email Gmail ho bisogno di accesso.
Scegli:
  [A] Accedi con Google (OAuth)
  [B] Inserisci App Password Gmail
  [C] Usa email AI Studio (noreply@aistudio.it) invece
```

> **User selects: [A] Accedi con Google (OAuth)**  
> OAuth flow completes → access token stored for session only, not persisted.

**Stacy output → routes to Gianni:**
```json
{
  "intent": "pdf_creation_and_email",
  "product_type": "pdf_document",
  "specs": {
    "title": "funziona",
    "content": "title_only"
  },
  "delivery": {
    "method": "email",
    "to": "stekkino@hotmail.it",
    "from": "gmail_oauth",
    "oauth_token": "[SESSION_TOKEN]"
  }
}
```

---

## Step 2 — Gianni analyses requirements

**Agent:** Gianni (Request-Analyzer)

| Check | Result |
|-------|--------|
| Complexity | Very low — single-title PDF |
| PDF generation tool | `fpdf2` (Python) or `reportlab` |
| Email delivery | Gmail API with OAuth token |
| External dependencies | Gmail API · PDF library |
| Estimated build time | < 10 sec |
| Blockers | None — OAuth token available |

**Gianni output → routes to Chiara:**
```json
{
  "pdf_tool": "fpdf2",
  "email_api": "gmail_api",
  "ready_to_generate": true
}
```

---

## Step 3 — Chiara generates the product

**Agent:** Chiara (Product-Generator)

Chiara runs the PDF generation script:

```python
from fpdf import FPDF

pdf = FPDF()
pdf.add_page()
pdf.set_font("Helvetica", "B", size=48)
pdf.set_y(120)  # vertically centred
pdf.cell(0, 20, "funziona", align="C")
pdf.output("funziona.pdf")
```

**PDF output:**
```
┌──────────────────────────────────────┐
│                                      │
│                                      │
│                                      │
│              funziona                │
│                                      │
│                                      │
│                                      │
└──────────────────────────────────────┘
  A4 · 1 page · Helvetica Bold 48pt
```

Chiara then prepares the Gmail API call:

```python
import base64
from email.mime.multipart import MIMEMultipart
from email.mime.base import MIMEBase
from email.mime.text import MIMEText
from email import encoders
from googleapiclient.discovery import build

def send_pdf_via_gmail(oauth_token, to, pdf_path):
    service = build("gmail", "v1", credentials=oauth_token)

    msg = MIMEMultipart()
    msg["To"] = to
    msg["Subject"] = "funziona"

    msg.attach(MIMEText("In allegato il tuo PDF.", "plain"))

    with open(pdf_path, "rb") as f:
        part = MIMEBase("application", "octet-stream")
        part.set_payload(f.read())
        encoders.encode_base64(part)
        part.add_header("Content-Disposition", 'attachment; filename="funziona.pdf"')
        msg.attach(part)

    raw = base64.urlsafe_b64encode(msg.as_bytes()).decode()
    service.users().messages().send(userId="me", body={"raw": raw}).execute()

send_pdf_via_gmail(oauth_token="[SESSION_TOKEN]",
                   to="stekkino@hotmail.it",
                   pdf_path="funziona.pdf")
```

**Chiara → routes to Stacy (QA):**
```json
{
  "pdf_file": "funziona.pdf",
  "pdf_size_kb": 8,
  "email_prepared": true,
  "ready_for_qa": true
}
```

---

## Step 4 — Stacy runs QA

**Agent:** Stacy (QA-Agent)

| Check | Result |
|-------|--------|
| PDF opens without errors | ✅ |
| Title text matches "funziona" exactly | ✅ |
| PDF is 1 page only | ✅ |
| Recipient email is valid format | ✅ `stekkino@hotmail.it` |
| Sender OAuth token is active | ✅ |
| Email subject set | ✅ "funziona" |
| Attachment included in email draft | ✅ |
| No sensitive data leaked in email body | ✅ |

**QA verdict:** PASS — no issues

**Stacy → routes to Marco:**
```json
{ "qa_passed": true, "ready_for_payment": true }
```

---

## Step 5 — Marco handles payment

**Agent:** Marco (Transaction-Manager)

| Item | Value |
|------|-------|
| Product | PDF document (1 page) + email delivery |
| Price | €1.90 |
| Payment method | Tap card |
| Status | ✅ Confirmed |
| Receipt ID | REC-20260523-002 |
| Digital receipt | Sent to user's Gmail (same session) |

**Marco → routes to Francesca:**
```json
{ "payment_confirmed": true, "receipt_id": "REC-20260523-002" }
```

---

## Step 6 — Francesca delivers the output

**Agent:** Francesca (Delivery-Agent)

**Actions taken:**
1. Triggered `send_pdf_via_gmail()` with the session OAuth token
2. Gmail API confirms `messageId: 18f3a2c9d4e1b567` — message sent
3. Displayed confirmation on dispenser screen
4. OAuth session token discarded (not stored)
5. Collected post-delivery feedback prompt

---

## Final Output

**On dispenser screen:**
```
✅ EMAIL INVIATA

Da:    luigi.vinegar@gmail.com
A:     stekkino@hotmail.it
Ogg:   funziona
Alleg: funziona.pdf (8 KB)

Ricevuta: REC-20260523-002

Feedback? → bit.ly/aisma-feedback
```

**What stekkino@hotmail.it receives:**
```
Da:      luigi.vinegar@gmail.com
Oggetto: funziona

In allegato il tuo PDF.

[📎 funziona.pdf  8 KB]
```

---

## Process Summary

| Step | Agent | Time | Status |
|------|-------|------|--------|
| 1. Input capture + OAuth prompt | Stacy | ~8 sec (incl. user OAuth) | ✅ |
| 2. Requirements analysis | Gianni | ~3 sec | ✅ |
| 3. PDF generation + email prep | Chiara | ~5 sec | ✅ |
| 4. Quality assurance | Stacy | ~5 sec | ✅ |
| 5. Payment | Marco | ~15 sec | ✅ |
| 6. Email delivery | Francesca | ~4 sec | ✅ |
| **Total** | | **~40 sec** | **✅ DONE** |

---

> **Simulation result:** Process works end to end. From raw text input to PDF delivered via Gmail in under 1 minute.  
> **Security note:** OAuth token used for single session only — never stored or logged by the system.
