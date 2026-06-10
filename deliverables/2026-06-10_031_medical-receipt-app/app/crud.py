"""Database CRUD operations."""
from __future__ import annotations

from typing import Optional, Sequence

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.models import Receipt
from app.schemas import DashboardSummary, DEDUCTIBLE_TYPES, ReceiptCreate, ReceiptUpdate

_FRANCHISE = 129.11
_DEDUCTION_RATE = 0.19


def create_receipt(db: Session, data: ReceiptCreate) -> Receipt:
    receipt = Receipt(**data.model_dump())
    db.add(receipt)
    db.commit()
    db.refresh(receipt)
    return receipt


def get_receipt(db: Session, receipt_id: str) -> Optional[Receipt]:
    return db.query(Receipt).filter(Receipt.id == receipt_id).first()


def list_receipts(
    db: Session,
    *,
    fiscal_year: Optional[int] = None,
    expense_type: Optional[str] = None,
    status: Optional[str] = None,
    search: Optional[str] = None,
    limit: int = 200,
    offset: int = 0,
) -> Sequence[Receipt]:
    q = db.query(Receipt)
    if fiscal_year:
        q = q.filter(Receipt.fiscal_year == fiscal_year)
    if expense_type:
        q = q.filter(Receipt.expense_type == expense_type)
    if status:
        q = q.filter(Receipt.status == status)
    if search:
        like = f"%{search}%"
        q = q.filter(
            Receipt.provider_name.ilike(like)
            | Receipt.description.ilike(like)
            | Receipt.receipt_number.ilike(like)
        )
    return q.order_by(Receipt.date.desc(), Receipt.created_at.desc()).limit(limit).offset(offset).all()


def update_receipt(db: Session, receipt_id: str, data: ReceiptUpdate) -> Optional[Receipt]:
    receipt = get_receipt(db, receipt_id)
    if not receipt:
        return None
    for field, value in data.model_dump(exclude_unset=True).items():
        setattr(receipt, field, value)
    db.commit()
    db.refresh(receipt)
    return receipt


def delete_receipt(db: Session, receipt_id: str) -> bool:
    receipt = get_receipt(db, receipt_id)
    if not receipt:
        return False
    db.delete(receipt)
    db.commit()
    return True


def get_dashboard(db: Session, fiscal_year: int) -> DashboardSummary:
    receipts = list_receipts(db, fiscal_year=fiscal_year)
    confirmed = [r for r in receipts if r.status == "confirmed"]
    pending = len([r for r in receipts if r.status == "pending_review"])

    total_amount = sum(float(r.total_amount or 0) for r in confirmed)
    total_deductible = sum(
        float(r.deductible_amount or r.total_amount or 0)
        for r in confirmed
        if r.tax_deductible
    )
    taxable_base = max(0.0, total_deductible - _FRANCHISE)
    estimated_saving = round(taxable_base * _DEDUCTION_RATE, 2)

    by_type: dict[str, float] = {}
    for r in confirmed:
        by_type[r.expense_type] = by_type.get(r.expense_type, 0.0) + float(r.total_amount or 0)

    return DashboardSummary(
        fiscal_year=fiscal_year,
        total_receipts=len(confirmed),
        total_amount=round(total_amount, 2),
        total_deductible=round(total_deductible, 2),
        estimated_tax_saving=estimated_saving,
        by_type=by_type,
        pending_review=pending,
    )


def available_years(db: Session) -> list[int]:
    rows = db.query(Receipt.fiscal_year).distinct().order_by(Receipt.fiscal_year.desc()).all()
    return [r[0] for r in rows]
