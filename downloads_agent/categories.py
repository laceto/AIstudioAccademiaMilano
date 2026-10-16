"""Extension -> category folder. Unknown extensions return None and are left alone."""
from pathlib import Path
from typing import Optional

CATEGORIES = {
    "Documents": {".pdf", ".doc", ".docx", ".txt", ".rtf", ".odt", ".xls", ".xlsx", ".csv", ".ppt", ".pptx", ".md", ".epub"},
    "Images": {".jpg", ".jpeg", ".png", ".gif", ".webp", ".bmp", ".svg", ".heic", ".tif", ".tiff"},
    "Video": {".mp4", ".mkv", ".mov", ".avi", ".webm"},
    "Audio": {".mp3", ".wav", ".flac", ".m4a", ".ogg"},
    "Archives": {".zip", ".rar", ".7z", ".tar", ".gz"},
    "Installers": {".exe", ".msi", ".msix", ".dmg", ".iso"},
}
PARTIAL_EXTS = {".crdownload", ".part", ".tmp", ".download", ".partial"}
IGNORED_NAMES = {"desktop.ini", "thumbs.db"}

_BY_EXT = {ext: cat for cat, exts in CATEGORIES.items() for ext in exts}


def classify(name: str) -> Optional[str]:
    return _BY_EXT.get(Path(name).suffix.lower())
