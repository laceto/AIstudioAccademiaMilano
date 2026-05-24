# Pricing Runbook

Source of truth: `config/global_settings.json` → `pricing` key.
Marco enforces these prices. **Unknown products block delivery and escalate to Luigi.**

---

## Price Table

| Product SKU | Price | Notes |
|-------------|-------|-------|
| `static_landing_page` | €9.90 | HTML/Tailwind, Vercel deploy |
| `premium_landing_page` | €29.90 | + Decap CMS, animations, JSON-LD |
| `commercial_landing_page` | €45.90 | + order webhook, calendar integration |
| `pdf_document` | €1.90 | fpdf2, any content |
| `invoice_pdf` | €3.90 | InvoiceTemplate, audit-logged |
| `strategic_report` | €4.90 | Markdown + risk agents, disclaimer required |
| `chatbot_app` | €19.90 | Streamlit + OpenAI, Streamlit Cloud deploy |
| `email_delivery` | €0.50 | Per send, Gmail API |
| `rag_knowledge_base` | €29.90 | Embeddings + retrieval + Streamlit UI |
| `calendar_integration` | €14.90 | Any calendar provider (Google/MS/Apple) |
| `unknown_product` | **null** | **Blocks delivery — escalate to Luigi** |

---

## Rules

1. **Marco never guesses.** If the product type isn't in the table → `unknown_product: null` → delivery blocked → Luigi sets price.
2. **Pricing adequacy ratio** `actual_price / fair_price < 0.85` → Marco flags P1.
3. **Stacy classifies intent first.** Gianni confirms stack. Marco prices after QA passes.
4. **Bundles:** price the dominant SKU + add-ons (e.g. landing page + email delivery = €9.90 + €0.50).
5. **R&D / internal work:** Marco voids invoice, logs as €0.00, audit still written.

---

## Escalation Protocol

```
Unknown product detected
    ↓
Marco blocks delivery
    ↓
Luigi reviews (sets price or voids)
    ↓
Marco resumes with approved price
    ↓
Audit log records Luigi override
```

---

## Price History

| SKU | Set by | Date | Notes |
|-----|--------|------|-------|
| `premium_landing_page` | Luigi | 2026-05-24 | €29.90 — above DA floor of €24.90 |
| `commercial_landing_page` | Luigi | 2026-05-24 | €45.90 — above APD ceiling of €39.90, DA veto overridden |
