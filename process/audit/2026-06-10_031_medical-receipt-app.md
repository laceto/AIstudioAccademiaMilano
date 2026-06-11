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
  - name: V2 Team
    role: review
    action: API Product Designer + Core Architect + Devil's Advocate + Quality Reliability Lead — 36 tests, all P0–P3 issues resolved
    duration_sec: 0
    status: completed
  - name: Francesca
    role: delivery
    action: Railway deployment config (railway.toml, nixpacks.toml, env-based DB/storage paths)
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

## Tests Passed (36/36)

- SQLite CRUD: create, list, dashboard, fiscal years, delete order
- Franchise math: €129.11 threshold, 19% rate, strict `is True` guard for None deductibility
- Schema validation: ISO date, Literal status/expense_type, 3-state tax_deductible
- Export: Excel (openpyxl) + PDF (reportlab) with 730 riepilogo
- Storage: size limit (20 MB), extension validation, save/load/delete
- Extractor: no-API-key fallback, JSON decode error, happy path, null deductibility preserved, APIError propagation (all mocked)
- API: health, upload size/extension guard, delete order (DB first), confirm endpoint, JSON summary export

## Railway Deployment

- `railway.toml` + `nixpacks.toml`: Nixpacks Python 3.11, `streamlit run --server.port $PORT`
- `.streamlit/config.toml`: headless, CORS off
- `DATABASE_URL` env var: auto-fixes `postgres://` → `postgresql://`; defaults to local SQLite
- `UPLOADS_DIR` env var: points to Railway Volume mount path
- Persistent storage: mount Volume at `/data`, set `DATABASE_URL=sqlite:////data/receipts.db` and `UPLOADS_DIR=/data/uploads`
