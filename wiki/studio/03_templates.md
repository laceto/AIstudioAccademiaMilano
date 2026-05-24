# Template Library

Reusable building blocks extracted from delivered requests. Use these first — don't rebuild from scratch.

---

## PDF — Invoice Template

**Path:** `templates/pdf/invoice_standard.py`
**Class:** `InvoiceTemplate`
**Produces:** Valid PDF bytes via fpdf2

```python
from templates.pdf.invoice_standard import InvoiceTemplate
pdf = InvoiceTemplate(
    invoice_id="INV-012",
    client_name="Mario Rossi",
    items=[{"description": "Static landing page", "price": 9.90}]
)
pdf.save("invoice.pdf")
```

**First used:** Request 003

---

## Streamlit — Chatbot Template

**Path:** `templates/streamlit/chatbot.py`
**Class:** `ChatbotTemplate`
**Produces:** Streamlit app with streaming, chat history, API key handling

```python
from templates.streamlit.chatbot import ChatbotTemplate
app = ChatbotTemplate(provider="openai", model="gpt-4o-mini")
app.run()
```

**First used:** Request 005

---

## Web — Landing Page Base

**Path:** `templates/web/landing_page_base.html`
**Produces:** HTML/Tailwind/AlpineJS landing page with Decap CMS hooks
**Features:** JSON-LD LocalBusiness, Open Graph meta, contact form sentinel, responsive

**First used:** Request 011 (extracted from Bakery v2)

---

## Web — Order Webhook

**Path:** `templates/web/order_webhook.py`
**Produces:** Flask webhook that receives orders → Gmail notification + Google Calendar event
**Security:** HMAC signature validation, input sanitisation

```bash
python templates/web/order_webhook.py  # runs on port 5000
```

**First used:** Request 011

---

## Web — Decap CMS Config

**Path:** `templates/web/decap_cms_config_minimal.yml`
**Produces:** Minimal Decap CMS config for GitHub-backed content editing
**Requires:** GitHub OAuth app + Netlify Identity (or self-hosted)

**First used:** Request 011
