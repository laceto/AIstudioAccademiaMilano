"""Single source of truth for tax constants, upload limits, and domain values."""
FRANCHISE_EUR: float = 129.11       # Art. 15 TUIR annual non-deductible franchise
DEDUCTION_RATE: float = 0.19        # 19% tax deduction rate

MAX_UPLOAD_BYTES: int = 20 * 1024 * 1024   # 20 MB

ALLOWED_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp", ".pdf"}

ALLOWED_MIME_TYPES = {
    "image/jpeg",
    "image/png",
    "image/webp",
    "application/pdf",
}

RECEIPT_STATUSES = {"pending_review", "confirmed", "rejected"}

EXPENSE_TYPE_VALUES = {"farmaco", "visita", "esame", "ticket", "dentista", "altro"}
