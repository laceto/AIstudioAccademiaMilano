---
request_id: "031"
date: "2026-06-10"
intent: unknown_product
slug: medical-receipt-app
outcome: success
product_key: medical_receipt_vault
price: 0.00
agents_invoked:
  - name: Gianni
    role: technical_scoping
    action: designed FastAPI + Streamlit + SQLite + OpenAI Vision architecture
    duration_sec: 0
    status: completed
  - name: Chiara
    role: implementation
    action: built full application (API, DB, extractor, export, Streamlit UI)
    duration_sec: 0
    status: completed
skills_used: []
learning_flags:
  new_skills: []
  new_mcp: []
  risk_score: 1
---

# Medical Receipt Vault — Build Log

## Deliverable

`deliverables/2026-06-10_031_medical-receipt-app/`

Full-stack application for capturing, extracting, storing, and exporting Italian medical receipts (scontrini sanitari) for 730 tax declaration purposes.

## Architecture

- **Backend**: FastAPI REST API (`api.py`) — 12 endpoints
- **Frontend**: Streamlit web app (`streamlit_app.py`) — mobile-optimised, 5 tabs
- **Database**: SQLite via SQLAlchemy (`data/receipts.db`)
- **AI Extraction**: OpenAI GPT-4o Vision (`app/extractor.py`)
- **Export**: Excel (openpyxl) + PDF (reportlab) with Italian 730 deductible summary

## Key Features

- Photo capture via smartphone camera (`st.camera_input`)
- File upload: JPEG, PNG, WebP, PDF
- Automatic OCR extraction: date, provider, P.IVA, expense type, amount, deductibility
- Manual review/correction screen before saving
- Organized by fiscal year
- Search by provider/description/receipt number
- Dashboard: totals, deductible estimate, 19% tax saving calculation, by-category chart
- Export to Excel (.xlsx) and PDF with 730 riepilogo fiscale
- Graceful fallback when no OPENAI_API_KEY

## Italian 730 Logic

- Deductible types: farmaco, visita, esame, ticket, dentista
- Franchise: €129.11/year (Art. 15 TUIR)
- Rate: 19% on (total_deductible - franchise)
- Estimated saving shown in dashboard and PDF export

## Tests Passed

- All imports
- SQLite CRUD (create, list, dashboard, years)
- Excel export: 6361 bytes
- PDF export: 3022 bytes
- FastAPI health, list, dashboard, export endpoints
