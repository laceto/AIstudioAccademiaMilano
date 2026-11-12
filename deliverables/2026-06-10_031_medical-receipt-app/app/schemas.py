from __future__ import annotations

import re
from datetime import datetime
from typing import Any, Literal, Optional

from pydantic import BaseModel, field_validator

from app.constants import EXPENSE_TYPE_VALUES, RECEIPT_STATUSES

EXPENSE_TYPES = {
    "farmaco": "Farmaco",
    "visita": "Visita medica",
    "esame": "Esame diagnostico",
    "ticket": "Ticket SSN",
    "dentista": "Dentista",
    "altro": "Altro",
}

DEDUCTIBLE_TYPES = {"farmaco", "visita", "esame", "ticket", "dentista"}

PAYMENT_METHODS = [
    "Contanti", "Carta di credito", "Carta di debito", "Bancomat",
    "Bonifico", "Satispay", "PayPal", "Altro",
]

ReceiptStatus = Literal["pending_review", "confirmed", "rejected"]
ExpenseType = Literal["farmaco", "visita", "esame", "ticket", "dentista", "altro"]

_ISO_DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")


def _validate_iso_date(v: Optional[str]) -> Optional[str]:
    if v is None:
        return v
    if not _ISO_DATE_RE.match(v):
        raise ValueError(f"date must be YYYY-MM-DD, got '{v}'")
    return v


class LineItem(BaseModel):
    description: str
    quantity: float = 1.0
    unit_price: Optional[float] = None
    total: float


class ExtractionResult(BaseModel):
    date: Optional[str] = None
    receipt_number: Optional[str] = None
    provider_name: Optional[str] = None
    provider_tax_id: Optional[str] = None
    expense_type: Optional[str] = "altro"
    description: Optional[str] = None
    payment_method: Optional[str] = None
    total_amount: Optional[float] = None
    deductible_amount: Optional[float] = None
    tax_deductible: Optional[bool] = None   # None = unknown/uncertain
    line_items: Optional[list[LineItem]] = None
    confidence: float = 0.0
    pages_extracted: int = 1


class ReceiptCreate(BaseModel):
    fiscal_year: int
    date: Optional[str] = None
    receipt_number: Optional[str] = None
    provider_name: str
    provider_tax_id: Optional[str] = None
    expense_type: str = "altro"
    description: Optional[str] = None
    payment_method: Optional[str] = None
    total_amount: float = 0.0
    deductible_amount: Optional[float] = None
    tax_deductible: Optional[bool] = None   # None = "da verificare"
    line_items: Optional[list[dict]] = None
    notes: Optional[str] = None
    original_file_path: Optional[str] = None
    file_type: Optional[str] = None
    raw_extraction: Optional[dict] = None
    status: ReceiptStatus = "pending_review"

    @field_validator("date", mode="before")
    @classmethod
    def validate_date(cls, v):
        return _validate_iso_date(v)

    @field_validator("expense_type", mode="before")
    @classmethod
    def validate_expense_type(cls, v):
        if v not in EXPENSE_TYPE_VALUES:
            return "altro"
        return v

    @field_validator("status", mode="before")
    @classmethod
    def validate_status(cls, v):
        if v not in RECEIPT_STATUSES:
            raise ValueError(f"status must be one of {RECEIPT_STATUSES}")
        return v


class ReceiptUpdate(BaseModel):
    fiscal_year: Optional[int] = None
    date: Optional[str] = None
    receipt_number: Optional[str] = None
    provider_name: Optional[str] = None
    provider_tax_id: Optional[str] = None
    expense_type: Optional[str] = None
    description: Optional[str] = None
    payment_method: Optional[str] = None
    total_amount: Optional[float] = None
    deductible_amount: Optional[float] = None
    tax_deductible: Optional[bool] = None
    line_items: Optional[list[dict]] = None
    notes: Optional[str] = None
    status: Optional[ReceiptStatus] = None

    @field_validator("date", mode="before")
    @classmethod
    def validate_date(cls, v):
        return _validate_iso_date(v)

    @field_validator("expense_type", mode="before")
    @classmethod
    def validate_expense_type(cls, v):
        if v is not None and v not in EXPENSE_TYPE_VALUES:
            return "altro"
        return v


class ReceiptOut(BaseModel):
    id: str
    fiscal_year: int
    date: Optional[str]
    receipt_number: Optional[str]
    provider_name: str
    provider_tax_id: Optional[str]
    expense_type: str
    description: Optional[str]
    payment_method: Optional[str]
    total_amount: float
    deductible_amount: Optional[float]
    tax_deductible: Optional[bool]
    line_items: Optional[list[dict]]
    original_file_path: Optional[str]
    file_type: Optional[str]
    status: str
    notes: Optional[str]
    created_at: datetime

    model_config = {"from_attributes": True}


class DashboardSummary(BaseModel):
    fiscal_year: int
    total_receipts: int
    total_amount: float
    total_deductible: float
    estimated_tax_saving: float
    by_type: dict[str, float]
    pending_review: int
    unknown_deductibility: int


class TaxSummary(BaseModel):
    fiscal_year: int
    total_receipts: int
    total_amount: float
    total_deductible: float
    franchise_eur: float
    taxable_base: float
    estimated_saving: float
    by_type: dict[str, float]
