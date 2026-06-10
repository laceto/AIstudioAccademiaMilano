"""FastAPI REST API for Medical Receipt Vault."""
from __future__ import annotations

import io
import sys
from pathlib import Path
from typing import Optional

sys.path.insert(0, str(Path(__file__).parent))

from fastapi import Depends, FastAPI, File, Form, HTTPException, Query, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import Response, StreamingResponse
from sqlalchemy.orm import Session

from app.crud import (
    available_years,
    create_receipt,
    delete_receipt,
    get_dashboard,
    get_receipt,
    list_receipts,
    update_receipt,
)
from app.database import get_db, init_db
from app.export import to_excel, to_pdf_summary
from app.extractor import extract_from_image, extract_from_pdf
from app.schemas import DashboardSummary, ExtractionResult, ReceiptCreate, ReceiptOut, ReceiptUpdate
from app.storage import delete_file, get_mime_type, load_file, save_file

init_db()

app = FastAPI(
    title="Medical Receipt Vault",
    description="API per la gestione delle ricevute sanitarie e la preparazione del 730",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
def health():
    return {"status": "ok"}


@app.post("/receipts/extract", response_model=ExtractionResult)
async def extract_receipt(file: UploadFile = File(...)):
    content = await file.read()
    if file.filename and file.filename.lower().endswith(".pdf"):
        return extract_from_pdf(content)
    return extract_from_image(content)


@app.post("/receipts/upload", response_model=ReceiptOut, status_code=201)
async def upload_receipt(
    file: UploadFile = File(...),
    fiscal_year: int = Form(...),
    auto_extract: bool = Form(True),
    db: Session = Depends(get_db),
):
    content = await file.read()
    relative_path, file_type = save_file(content, file.filename or "receipt", fiscal_year)

    extraction = None
    if auto_extract:
        if file_type == "pdf":
            extraction = extract_from_pdf(content)
        else:
            extraction = extract_from_image(content)

    data = ReceiptCreate(
        fiscal_year=fiscal_year,
        provider_name=extraction.provider_name or "Da definire" if extraction else "Da definire",
        date=extraction.date if extraction else None,
        receipt_number=extraction.receipt_number if extraction else None,
        provider_tax_id=extraction.provider_tax_id if extraction else None,
        expense_type=extraction.expense_type or "altro" if extraction else "altro",
        description=extraction.description if extraction else None,
        payment_method=extraction.payment_method if extraction else None,
        total_amount=extraction.total_amount or 0.0 if extraction else 0.0,
        deductible_amount=extraction.deductible_amount if extraction else None,
        tax_deductible=extraction.tax_deductible if extraction else True,
        line_items=[item.model_dump() for item in (extraction.line_items or [])] if extraction else None,
        original_file_path=relative_path,
        file_type=file_type,
        raw_extraction=extraction.model_dump() if extraction else None,
        status="pending_review" if auto_extract and extraction and extraction.confidence > 0 else "pending_review",
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


@app.put("/receipts/{receipt_id}", response_model=ReceiptOut)
def update_receipt_endpoint(receipt_id: str, data: ReceiptUpdate, db: Session = Depends(get_db)):
    r = update_receipt(db, receipt_id, data)
    if not r:
        raise HTTPException(404, "Ricevuta non trovata")
    return r


@app.delete("/receipts/{receipt_id}", status_code=204)
def delete_receipt_endpoint(receipt_id: str, db: Session = Depends(get_db)):
    r = get_receipt(db, receipt_id)
    if not r:
        raise HTTPException(404, "Ricevuta non trovata")
    if r.original_file_path:
        delete_file(r.original_file_path)
    deleted = delete_receipt(db, receipt_id)
    if not deleted:
        raise HTTPException(500, "Eliminazione fallita")


@app.get("/receipts/{receipt_id}/image")
def get_receipt_image(receipt_id: str, db: Session = Depends(get_db)):
    r = get_receipt(db, receipt_id)
    if not r or not r.original_file_path:
        raise HTTPException(404, "Immagine non trovata")
    content = load_file(r.original_file_path)
    if not content:
        raise HTTPException(404, "File non trovato su disco")
    mime = get_mime_type(r.original_file_path)
    return Response(content=content, media_type=mime)


@app.get("/dashboard/{fiscal_year}", response_model=DashboardSummary)
def dashboard(fiscal_year: int, db: Session = Depends(get_db)):
    return get_dashboard(db, fiscal_year)


@app.get("/years")
def get_years(db: Session = Depends(get_db)):
    return available_years(db)


@app.get("/export/excel/{fiscal_year}")
def export_excel(fiscal_year: int, db: Session = Depends(get_db)):
    receipts = list_receipts(db, fiscal_year=fiscal_year, status="confirmed")
    xlsx = to_excel(receipts, fiscal_year)
    return Response(
        content=xlsx,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f"attachment; filename=spese_sanitarie_{fiscal_year}.xlsx"},
    )


@app.get("/export/pdf/{fiscal_year}")
def export_pdf(fiscal_year: int, db: Session = Depends(get_db)):
    receipts = list_receipts(db, fiscal_year=fiscal_year, status="confirmed")
    pdf = to_pdf_summary(receipts, fiscal_year)
    return Response(
        content=pdf,
        media_type="application/pdf",
        headers={"Content-Disposition": f"attachment; filename=spese_sanitarie_{fiscal_year}.pdf"},
    )


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("api:app", host="0.0.0.0", port=8000, reload=True)
