"""File storage — local disk backend with size/extension validation."""
from __future__ import annotations

import abc
import os
import uuid
from pathlib import Path

from app.constants import ALLOWED_EXTENSIONS, MAX_UPLOAD_BYTES

def _default_uploads_dir() -> Path:
    env = os.getenv("UPLOADS_DIR")
    return Path(env) if env else Path(__file__).parent.parent / "uploads"

_UPLOADS_DIR = _default_uploads_dir()


class StorageBackend(abc.ABC):
    @abc.abstractmethod
    def save(self, file_bytes: bytes, original_filename: str, fiscal_year: int) -> tuple[str, str]:
        """Save bytes. Returns (relative_path, file_type)."""

    @abc.abstractmethod
    def load(self, path: str) -> bytes | None:
        """Return file bytes or None if not found."""

    @abc.abstractmethod
    def delete(self, path: str) -> None:
        """Delete file; silently no-op if missing."""


class LocalStorageBackend(StorageBackend):
    def __init__(self, base_dir: Path = _UPLOADS_DIR):
        self._base = base_dir

    def save(self, file_bytes: bytes, original_filename: str, fiscal_year: int) -> tuple[str, str]:
        ext = Path(original_filename).suffix.lower()
        if ext not in ALLOWED_EXTENSIONS:
            raise ValueError(f"Formato '{ext}' non consentito. Formati supportati: {', '.join(sorted(ALLOWED_EXTENSIONS))}")
        if len(file_bytes) > MAX_UPLOAD_BYTES:
            raise ValueError(f"File troppo grande ({len(file_bytes) // (1024*1024)} MB). Massimo {MAX_UPLOAD_BYTES // (1024*1024)} MB.")

        file_type = "pdf" if ext == ".pdf" else "image"
        year_dir = self._base / str(fiscal_year)
        year_dir.mkdir(parents=True, exist_ok=True)

        dest = year_dir / f"{uuid.uuid4()}{ext}"
        dest.write_bytes(file_bytes)

        relative = str(dest.relative_to(self._base.parent))
        return relative, file_type

    def load(self, path: str) -> bytes | None:
        full = self._base.parent / path
        return full.read_bytes() if full.exists() else None

    def delete(self, path: str) -> None:
        full = self._base.parent / path
        if full.exists():
            full.unlink()


_default_backend: StorageBackend = LocalStorageBackend()


def save_file(file_bytes: bytes, original_filename: str, fiscal_year: int) -> tuple[str, str]:
    return _default_backend.save(file_bytes, original_filename, fiscal_year)


def load_file(relative_path: str) -> bytes | None:
    return _default_backend.load(relative_path)


def delete_file(relative_path: str) -> None:
    _default_backend.delete(relative_path)


def get_mime_type(relative_path: str) -> str:
    return {
        ".pdf": "application/pdf",
        ".jpg": "image/jpeg",
        ".jpeg": "image/jpeg",
        ".png": "image/png",
        ".heic": "image/heic",
        ".webp": "image/webp",
    }.get(Path(relative_path).suffix.lower(), "application/octet-stream")
