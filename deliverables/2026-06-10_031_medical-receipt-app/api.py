"""FastAPI REST API for Medical Receipt Vault."""
from __future__ import annotations

import logging
import os
import sys
from pathlib import Path
from typing import Optional

sys.path.insert(0, str(Path(__file__).parent))

from dotenv import load_dotenv

def _find_env() -> Path:
    here = Path(__file__).parent
    for candidate in [here / ".env", here.parent.parent.parent / ".env"]:
        if candidate.exists():
            return candidate
    return here / ".env"

load_dotenv(_find_env(), override=True)

from fastapi import Depends, FastAPI, File, Form, HTTPException, Query, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import Response
from sqlalchemy.orm import Session

from app.constants import ALLOWED_EXTENSIONS, MAX_UPLOAD_BYTES
from app.crud import (
    available_years,
    create_receipt,
    delete_receipt,
    get_dashboard,
    get_receipt,
    get_tax_summary,
    list_receipts,
    update_receipt,
)
from app.database import check_db_health, get_db, init_db
from app.export import to_excel, to_pdf_summary
from app.extractor import extract_from_image, extract_from_pdf
from app.schemas import (
    DashboardSummary, ExtractionResult, ReceiptCreate, ReceiptOut,
    ReceiptUpdate, TaxSummary,
)
from app.storage import delete_file, get_mime_type, load_file, save_file

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s — %(message)s")

init_db()

_CORS_ORIGINS = [o.strip() for o in os.getenv(
    "CORS_ORIGINS",
    "http://localhost:8501,http://localhost:8000,http://127.0.0.1:8501",
).split(",") if o.strip()]

app = FastAPI(
    title="Medical Receipt Vault",
    description="API per la gestione delle ricevute sanitarie e la preparazione del 730",
    version="1.1.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=_CORS_ORIGINS,
    allow_methods=["*"],
    allow_headers=["*"],
)


def _validate_upload(content: bytes, filename: str) -> None:
    if len(content) > MAX_UPLOAD_BYTES:
        raise HTTPException(413, f"File troppo grande. Massimo {MAX_UPLOAD_BYTES // (1024*1024)} MB.")
    ext = Path(filename).suffix.lower() if filename else ""
    if ext not in ALLOWED_EXTENSIONS:
        raise HTTPException(415, f"Tipo file non supportato '{ext}'. Formati: {', '.join(ALLOWED_EXTENSIONS)}")


@app.get("/health")
def health():
    db_ok = check_db_health()
    uploads_ok = (Path(__file__).parent / "uploads").exists()
    status = "ok" if db_ok and uploads_ok else "degraded"
    return {"status": status, "db": db_ok, "storage": uploads_ok}


@app.post("/receipts/extract", response_model=ExtractionResult)
async def extract_receipt(file: UploadFile = File(...)):
    content = await file.read()
    _validate_upload(content, file.filename or "")
    try:
        if (file.filename or "").lower().endswith(".pdf"):
            return extract_from_pdf(content)
        return extract_from_image(content)
    except Exception as exc:
        logger.error("Extraction failed: %s", exc)
        raise HTTPException(503, "Servizio di estrazione non disponibile. Inserisci i dati manualmente.")


@app.post("/receipts/upload", response_model=ReceiptOut, status_code=201)
async def upload_receipt(
    file: UploadFile = File(...),
    fiscal_year: int = Form(...),
    auto_extract: bool = Form(True),
    db: Session = Depends(get_db),
):
    content = await file.read()
    _validate_upload(content, file.filename or "")

    extraction = None
    if auto_extract:
        try:
            if (file.filename or "").lower().endswith(".pdf"):
                extraction = extract_from_pdf(content)
            else:
                extraction = extract_from_image(content)
        except Exception as exc:
            logger.error("Extraction error during upload: %s", exc)

    try:
        relative_path, file_type = save_file(content, file.filename or "receipt.jpg", fiscal_year)
    except ValueError as exc:
        raise HTTPException(400, str(exc))
    except OSError as exc:
        logger.error("Disk write failed: %s", exc)
        raise HTTPException(500, "Impossibile salvare il file. Controlla lo spazio su disco.")

    status = "pending_review" if extraction and extraction.confidence > 0 else "pending_review"
    data = ReceiptCreate(
        fiscal_year=fiscal_year,
        provider_name=(extraction.provider_name or "Da definire") if extraction else "Da definire",
        date=extraction.date if extraction else None,
        receipt_number=extraction.receipt_number if extraction else None,
        provider_tax_id=extraction.provider_tax_id if extraction else None,
        expense_type=(extraction.expense_type or "altro") if extraction else "altro",
        description=extraction.description if extraction else None,
        payment_method=extraction.payment_method if extraction else None,
        total_amount=(extraction.total_amount or 0.0) if extraction else 0.0,
        deductible_amount=extraction.deductible_amount if extraction else None,
        tax_deductible=extraction.tax_deductible if extraction else None,
        line_items=[i.model_dump() for i in (extraction.line_items or [])] if extraction else None,
        original_file_path=relative_path,
        file_type=file_type,
        raw_extraction=extraction.model_dump() if extraction else None,
        status=status,
    )
    return create_receipt(db, data)


@app.get("/receipts/", response_model=list[ReceiptOut])
def list_receipts_endpoint(
    fiscal_year: Optional[int] = Query(None),
    expense_type: Optional[str] = Query(None),
    status: Optional[str] = Query(None),
    search: Optional[str] = Query(None),
    limit: int = Query(200, le=1000),
    offset: int = Query(0),
    db: Session = Depends(get_db),
):
    return list_receipts(db, fiscal_year=fiscal_year, expense_type=expense_type,
                         status=status, search=search, limit=limit, offset=offset)


@app.get("/receipts/{receipt_id}", response_model=ReceiptOut)
def get_receipt_endpoint(receipt_id: str, db: Session = Depends(get_db)):
    r = get_receipt(db, receipt_id)
    if not r:
        raise HTTPException(404, "Ricevuta non trovata")
    return r


@app.patch("/receipts/{receipt_id}", response_model=ReceiptOut)
def patch_receipt_endpoint(receipt_id: str, data: ReceiptUpdate, db: Session = Depends(get_db)):
    r = update_receipt(db, receipt_id, data)
    if not r:
        raise HTTPException(404, "Ricevuta non trovata")
    return r


@app.post("/receipts/{receipt_id}/confirm", response_model=ReceiptOut)
def confirm_receipt(receipt_id: str, db: Session = Depends(get_db)):
    """One-tap confirmation — sets status to 'confirmed' without a full update body."""
    r = update_receipt(db, receipt_id, ReceiptUpdate(status="confirmed"))
    if not r:
        raise HTTPException(404, "Ricevuta non trovata")
    return r


@app.delete("/receipts/{receipt_id}", status_code=204)
def delete_receipt_endpoint(receipt_id: str, db: Session = Depends(get_db)):
    r = get_receipt(db, receipt_id)
    if not r:
        raise HTTPException(404, "Ricevuta non trovata")

    file_path = r.original_file_path

    deleted = delete_receipt(db, receipt_id)
    if not deleted:
        raise HTTPException(500, "Eliminazione DB fallita")

    if file_path:
        try:
            delete_file(file_path)
        except Exception as exc:
            logger.warning("DB row deleted but file removal failed (%s): %s", file_path, exc)


@app.get("/receipts/{receipt_id}/image")
def get_receipt_image(receipt_id: str, db: Session = Depends(get_db)):
    r = get_receipt(db, receipt_id)
    if not r or not r.original_file_path:
        raise HTTPException(404, "Immagine non trovata")
    content = load_file(r.original_file_path)
    if not content:
        raise HTTPException(404, "File non trovato su disco")
    return Response(content=content, media_type=get_mime_type(r.original_file_path))


@app.get("/dashboard/{fiscal_year}", response_model=DashboardSummary)
def dashboard(fiscal_year: int, db: Session = Depends(get_db)):
    return get_dashboard(db, fiscal_year)


@app.get("/years")
def get_years(db: Session = Depends(get_db)):
    return available_years(db)


@app.get("/export/summary/{fiscal_year}", response_model=TaxSummary)
def export_summary_json(fiscal_year: int, db: Session = Depends(get_db)):
    """Structured JSON tax summary — for programmatic consumption by mobile clients."""
    return get_tax_summary(db, fiscal_year)


@app.get("/export/excel/{fiscal_year}")
def export_excel(fiscal_year: int, db: Session = Depends(get_db)):
    receipts = list_receipts(db, fiscal_year=fiscal_year, status="confirmed")
    try:
        xlsx = to_excel(receipts, fiscal_year)
    except RuntimeError as exc:
        raise HTTPException(500, str(exc))
    return Response(
        content=xlsx,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f"attachment; filename=spese_sanitarie_{fiscal_year}.xlsx"},
    )


@app.get("/export/pdf/{fiscal_year}")
def export_pdf(fiscal_year: int, db: Session = Depends(get_db)):
    receipts = list_receipts(db, fiscal_year=fiscal_year, status="confirmed")
    try:
        pdf = to_pdf_summary(receipts, fiscal_year)
    except RuntimeError as exc:
        raise HTTPException(500, str(exc))
    return Response(
        content=pdf,
        media_type="application/pdf",
        headers={"Content-Disposition": f"attachment; filename=spese_sanitarie_{fiscal_year}.pdf"},
    )


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("api:app", host="0.0.0.0", port=8000, reload=True)
