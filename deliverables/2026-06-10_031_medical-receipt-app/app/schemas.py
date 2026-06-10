from __future__ import annotations

from datetime import datetime
from typing import Any, Optional

from pydantic import BaseModel, Field


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
    tax_deductible: Optional[bool] = True
    line_items: Optional[list[LineItem]] = None
    confidence: float = 0.0


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
    tax_deductible: bool = True
    line_items: Optional[list[dict]] = None
    notes: Optional[str] = None
    original_file_path: Optional[str] = None
    file_type: Optional[str] = None
    raw_extraction: Optional[dict] = None
    status: str = "confirmed"


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
    status: Optional[str] = None


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
    tax_deductible: bool
    line_items: Optional[Any]
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
    estimated_tax_saving: float          # 19% × (deductible - 129.11 franchise)
    by_type: dict[str, float]
    pending_review: int
