"""File storage — saves uploaded receipts to disk organized by fiscal year."""
from __future__ import annotations

import shutil
import uuid
from pathlib import Path

_UPLOADS_DIR = Path(__file__).parent.parent / "uploads"


def save_file(file_bytes: bytes, original_filename: str, fiscal_year: int) -> tuple[str, str]:
    """
    Save file bytes to uploads/<fiscal_year>/<uuid>.<ext>.
    Returns (relative_path, file_type).
    """
    ext = Path(original_filename).suffix.lower()
    file_type = "pdf" if ext == ".pdf" else "image"
    year_dir = _UPLOADS_DIR / str(fiscal_year)
    year_dir.mkdir(parents=True, exist_ok=True)

    filename = f"{uuid.uuid4()}{ext}"
    dest = year_dir / filename
    dest.write_bytes(file_bytes)

    relative = str(dest.relative_to(_UPLOADS_DIR.parent))
    return relative, file_type


def load_file(relative_path: str) -> bytes | None:
    full = _UPLOADS_DIR.parent / relative_path
    if full.exists():
        return full.read_bytes()
    return None


def delete_file(relative_path: str) -> None:
    full = _UPLOADS_DIR.parent / relative_path
    if full.exists():
        full.unlink()


def get_mime_type(relative_path: str) -> str:
    ext = Path(relative_path).suffix.lower()
    return {
        ".pdf": "application/pdf",
        ".jpg": "image/jpeg",
        ".jpeg": "image/jpeg",
        ".png": "image/png",
        ".heic": "image/heic",
        ".webp": "image/webp",
    }.get(ext, "application/octet-stream")
