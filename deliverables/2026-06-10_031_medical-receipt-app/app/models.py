import uuid
from datetime import datetime

from sqlalchemy import Boolean, Column, DateTime, Integer, JSON, Numeric, String, Text
from app.database import Base


class Receipt(Base):
    __tablename__ = "receipts"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    fiscal_year = Column(Integer, nullable=False, index=True)
    date = Column(String(10), nullable=True)          # ISO date string YYYY-MM-DD
    receipt_number = Column(String(100), nullable=True)
    provider_name = Column(String(255), nullable=False, index=True)
    provider_tax_id = Column(String(30), nullable=True)
    expense_type = Column(String(20), default="altro", index=True)
    description = Column(Text, nullable=True)
    payment_method = Column(String(50), nullable=True)
    total_amount = Column(Numeric(10, 2), nullable=False, default=0)
    deductible_amount = Column(Numeric(10, 2), nullable=True)
    tax_deductible = Column(Boolean, nullable=True)   # None = unknown/to-verify
    line_items = Column(JSON, nullable=True)
    original_file_path = Column(String(500), nullable=True)
    file_type = Column(String(10), nullable=True)     # "image" | "pdf"
    status = Column(String(20), default="pending_review", index=True)
    raw_extraction = Column(JSON, nullable=True)
    notes = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
