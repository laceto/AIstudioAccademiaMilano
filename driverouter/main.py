"""Drive semantic router: FastAPI + Google Drive API + APScheduler.

Watches the Drive inbox folder (default `05_In_Arrivo_Da_Smistare`), extracts text from each new file,
classifies it with `SemanticClassifier` and moves (optionally renames) it into the destination folder.

Run locally:  uvicorn driverouter.main:app --port 8000
Endpoints:    POST /sync-documents (header X-API-Key), GET /health
"""
from __future__ import annotations

import hmac
import io
import json
import logging
import os
import re
import sys
import threading
import time
import unicodedata
from contextlib import asynccontextmanager
from dataclasses import dataclass, field
from datetime import datetime, timezone

from fastapi import FastAPI, Header, HTTPException

from driverouter.classifier import (
    DEFAULT_MODEL,
    SemanticClassifier,
    SentenceTransformerEmbedder,
)

# ── Logging (JSON on stdout; App Service / Container Apps forward it to Log Analytics) ──────────

_STD_ATTRS = set(vars(logging.LogRecord("", 0, "", 0, "", None, None))) | {"message", "asctime"}


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        payload = {
            "ts": datetime.fromtimestamp(record.created, timezone.utc).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "msg": record.getMessage(),
        }
        payload.update({k: v for k, v in vars(record).items() if k not in _STD_ATTRS})
        if record.exc_info:
            payload["exc"] = self.formatException(record.exc_info)
        return json.dumps(payload, ensure_ascii=False, default=str)


def setup_logging() -> None:
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(JsonFormatter())
    root = logging.getLogger("driverouter")
    root.handlers = [handler]
    root.setLevel(os.getenv("LOG_LEVEL", "INFO"))
    root.propagate = False
    # Application Insights: only when the connection string is set and the package is installed.
    if os.getenv("APPLICATIONINSIGHTS_CONNECTION_STRING"):
        try:
            from azure.monitor.opentelemetry import configure_azure_monitor

            configure_azure_monitor(logger_name="driverouter")
        except ImportError:
            root.warning("azure-monitor-opentelemetry not installed; App Insights export disabled")


log = logging.getLogger("driverouter.main")

# ── Settings and secrets ───────────────────────────────────────────────────────────────────────

SECRET_NAMES = {  # env var -> Key Vault secret name
    "GOOGLE_CLIENT_ID": "google-client-id",
    "GOOGLE_CLIENT_SECRET": "google-client-secret",
    "GOOGLE_REFRESH_TOKEN": "google-refresh-token",
    "SYNC_API_KEY": "sync-api-key",
}


def _flag(name: str, default: str) -> bool:
    return os.getenv(name, default).strip().lower() in {"1", "true", "yes", "on"}


@dataclass
class Settings:
    inbox_path: str = field(default_factory=lambda: os.getenv("INBOX_FOLDER_PATH", "05_In_Arrivo_Da_Smistare"))
    inbox_id: str | None = field(default_factory=lambda: os.getenv("INBOX_FOLDER_ID") or None)
    root_id: str = field(default_factory=lambda: os.getenv("DRIVE_ROOT_FOLDER_ID", "root"))
    dry_run: bool = field(default_factory=lambda: _flag("DRY_RUN", "true"))
    rename: bool = field(default_factory=lambda: _flag("RENAME_FILES", "true"))
    ocr: bool = field(default_factory=lambda: _flag("DRIVE_OCR", "true"))
    create_missing: bool = field(default_factory=lambda: _flag("CREATE_MISSING_FOLDERS", "false"))
    max_files: int = field(default_factory=lambda: int(os.getenv("MAX_FILES_PER_RUN", "25")))
    max_download_mb: int = field(default_factory=lambda: int(os.getenv("MAX_DOWNLOAD_MB", "15")))
    interval_min: int = field(default_factory=lambda: int(os.getenv("SYNC_INTERVAL_MINUTES", "30")))


def load_secrets_from_key_vault() -> None:
    """Fill missing secret env vars from Key Vault.

    On App Service the secrets normally arrive already resolved through Key Vault references
    (`@Microsoft.KeyVault(...)` app settings). This fallback covers Container Apps / local runs:
    set KEY_VAULT_URL and authenticate with a managed identity or `az login`.
    """
    vault = os.getenv("KEY_VAULT_URL")
    missing = [k for k in SECRET_NAMES if not os.getenv(k)]
    if not vault or not missing:
        return
    from azure.identity import DefaultAzureCredential
    from azure.keyvault.secrets import SecretClient

    client = SecretClient(vault_url=vault, credential=DefaultAzureCredential())
    for env_name in missing:
        try:
            os.environ[env_name] = client.get_secret(SECRET_NAMES[env_name]).value
        except Exception as exc:  # never log the value, only which secret failed
            log.error("key vault secret unavailable", extra={"secret": SECRET_NAMES[env_name], "error": type(exc).__name__})


# ── Google Drive ───────────────────────────────────────────────────────────────────────────────

FOLDER_MIME = "application/vnd.google-apps.folder"
GDOC_MIME = "application/vnd.google-apps.document"
EXPORTS = {  # Google-native files are exported, not downloaded
    GDOC_MIME: "text/plain",
    "application/vnd.google-apps.spreadsheet": "text/csv",
    "application/vnd.google-apps.presentation": "text/plain",
}
# Formats Drive can convert to a Google Doc (OCR for images and scanned PDFs, text for Office files).
CONVERTIBLE = ("image/", "application/pdf", "application/msword", "application/vnd.openxmlformats-officedocument")
STATUS_KEY = "sr_status"  # appProperties marker set by this service


def build_drive_service():
    from google.oauth2.credentials import Credentials
    from googleapiclient.discovery import build

    creds = Credentials(
        token=None,
        refresh_token=os.environ["GOOGLE_REFRESH_TOKEN"],
        client_id=os.environ["GOOGLE_CLIENT_ID"],
        client_secret=os.environ["GOOGLE_CLIENT_SECRET"],
        token_uri="https://oauth2.googleapis.com/token",
        scopes=["https://www.googleapis.com/auth/drive"],
    )
    return build("drive", "v3", credentials=creds, cache_discovery=False)


def _q(value: str) -> str:
    return value.replace("\\", "\\\\").replace("'", "\\'")


class DriveClient:
    def __init__(self, service, settings: Settings):
        self.svc = service
        self.settings = settings
        self._folder_cache: dict[str, str] = {}

    def find_folder(self, path: str, create: bool = False) -> str | None:
        """Resolve 'A/B/C' under the configured root to a folder id."""
        if path in self._folder_cache:
            return self._folder_cache[path]
        parent = self.settings.root_id
        for part in [p for p in path.split("/") if p]:
            res = self.svc.files().list(
                q=f"name = '{_q(part)}' and '{parent}' in parents and mimeType = '{FOLDER_MIME}' and trashed = false",
                fields="files(id,name)", pageSize=2,
                supportsAllDrives=True, includeItemsFromAllDrives=True,
            ).execute()
            found = res.get("files", [])
            if found:
                parent = found[0]["id"]
            elif create:
                parent = self.svc.files().create(
                    body={"name": part, "mimeType": FOLDER_MIME, "parents": [parent]},
                    fields="id", supportsAllDrives=True,
                ).execute()["id"]
                log.info("folder created", extra={"path": path, "part": part})
            else:
                return None
        self._folder_cache[path] = parent
        return parent

    def list_inbox(self, inbox_id: str, limit: int) -> list[dict]:
        files, token = [], None
        while len(files) < limit:
            res = self.svc.files().list(
                q=f"'{inbox_id}' in parents and trashed = false and mimeType != '{FOLDER_MIME}'",
                fields="nextPageToken, files(id,name,mimeType,size,createdTime,appProperties)",
                orderBy="createdTime", pageSize=min(100, limit), pageToken=token,
                supportsAllDrives=True, includeItemsFromAllDrives=True,
            ).execute()
            files.extend(res.get("files", []))
            token = res.get("nextPageToken")
            if not token:
                break
        return files[:limit]

    def _download(self, file_id: str) -> bytes:
        from googleapiclient.http import MediaIoBaseDownload

        buf = io.BytesIO()
        downloader = MediaIoBaseDownload(buf, self.svc.files().get_media(fileId=file_id, supportsAllDrives=True))
        done = False
        while not done:
            _, done = downloader.next_chunk()
        return buf.getvalue()

    def _export(self, file_id: str, mime: str) -> str:
        data = self.svc.files().export(fileId=file_id, mimeType=mime).execute()
        return data.decode("utf-8", "replace") if isinstance(data, bytes) else str(data)

    def _convert_to_text(self, file_id: str, inbox_id: str) -> str:
        """Let Drive do the OCR/conversion: copy as a Google Doc, export its text, delete the copy."""
        tmp = self.svc.files().copy(
            fileId=file_id, ocrLanguage="it", supportsAllDrives=True, fields="id",
            body={"name": f"_sr_tmp_{file_id}", "mimeType": GDOC_MIME, "parents": [inbox_id],
                  "appProperties": {STATUS_KEY: "tmp"}},
        ).execute()["id"]
        try:
            return self._export(tmp, "text/plain")
        finally:
            self.svc.files().delete(fileId=tmp, supportsAllDrives=True).execute()

    def extract_text(self, f: dict, inbox_id: str) -> tuple[str, str]:
        """Return (text, method). Never raises for unsupported formats: falls back to the file name."""
        mime, fid = f["mimeType"], f["id"]
        if mime in EXPORTS:
            return self._export(fid, EXPORTS[mime]), "export"
        too_big = int(f.get("size") or 0) > self.settings.max_download_mb * 1024 * 1024
        if mime.startswith("text/") or mime == "application/json":
            if not too_big:
                return self._download(fid).decode("utf-8", "replace"), "download"
        if mime == "application/pdf" and not too_big:
            text = pdf_text(self._download(fid))
            if len(text.strip()) >= 50 or not self.settings.ocr:
                return text, "pypdf"
        if self.settings.ocr and mime.startswith(CONVERTIBLE):
            return self._convert_to_text(fid, inbox_id), "drive_ocr"
        return "", "name_only"

    def move(self, file_id: str, src: str, dest: str, new_name: str | None, props: dict) -> None:
        body = {"appProperties": props}
        if new_name:
            body["name"] = new_name
        self.svc.files().update(
            fileId=file_id, addParents=dest, removeParents=src, body=body,
            fields="id,parents,name", supportsAllDrives=True,
        ).execute()

    def mark(self, file_id: str, props: dict) -> None:
        self.svc.files().update(fileId=file_id, body={"appProperties": props}, fields="id", supportsAllDrives=True).execute()


def pdf_text(data: bytes, max_pages: int = 5) -> str:
    from pypdf import PdfReader

    try:
        reader = PdfReader(io.BytesIO(data))
        return "\n".join((page.extract_text() or "") for page in reader.pages[:max_pages])
    except Exception:
        return ""


# ── Naming ─────────────────────────────────────────────────────────────────────────────────────

_LEADING_DATE = re.compile(r"^\d{4}[-_.]?\d{2}[-_.]?\d{2}[-_ ]*")


def _slug(text: str, max_len: int = 60) -> str:
    text = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode()
    text = re.sub(r"[^A-Za-z0-9]+", "-", text).strip("-")
    return text[:max_len].rstrip("-") or "Documento"


def clean_name(original: str, category: str, created_time: str | None) -> str:
    """`YYYY-MM-DD_Categoria_Descrizione.ext` from the Drive creation date and the original name."""
    stem, dot, ext = original.rpartition(".")
    if not dot or not stem or len(ext) > 5 or " " in ext:
        stem, ext = original, ""  # no real extension (e.g. Google Docs)
    date = (created_time or datetime.now(timezone.utc).isoformat())[:10]
    stem = _LEADING_DATE.sub("", stem)
    if stem.lower().startswith(category.lower()):  # already renamed once
        stem = stem[len(category):]
    name = f"{date}_{category}_{_slug(stem)}"
    return f"{name}.{ext.lower()}" if ext else name


# ── Sync ───────────────────────────────────────────────────────────────────────────────────────


def sync_once(drive, classifier, settings: Settings, force: bool = False) -> dict:
    started = time.monotonic()
    inbox_id = settings.inbox_id or drive.find_folder(settings.inbox_path)
    if not inbox_id:
        raise RuntimeError(f"inbox folder not found: {settings.inbox_path}")

    summary = {"dry_run": settings.dry_run, "moved": 0, "unsure": 0, "skipped": 0, "errors": 0, "files": []}
    for f in drive.list_inbox(inbox_id, settings.max_files):
        status = (f.get("appProperties") or {}).get(STATUS_KEY)
        if status == "tmp" or (status == "unsure" and not force):
            summary["skipped"] += 1
            continue
        t0 = time.monotonic()
        try:
            text, method = drive.extract_text(f, inbox_id)
            name_hint = re.sub(r"[_\-.]+", " ", f["name"])
            result = classifier.classify(f"{name_hint}\n{text}")
            entry = {
                "file_id": f["id"], "file_name": f["name"], "method": method, "chars": len(text),
                "category": result.category, "similarity": result.similarity,
                "best": next(iter(result.scores), None), "runner_up": result.runner_up, "margin": result.margin,
            }
            if result.category is None:
                summary["unsure"] += 1
                entry["action"] = "left_in_inbox"
                if not settings.dry_run:
                    drive.mark(f["id"], {STATUS_KEY: "unsure", "sr_best": next(iter(result.scores), "")})
            else:
                dest = drive.find_folder(result.path, create=settings.create_missing)
                if not dest:
                    raise RuntimeError(f"destination folder not found: {result.path}")
                new_name = clean_name(f["name"], result.category, f.get("createdTime")) if settings.rename else None
                entry.update(action="moved", dest=result.path, new_name=new_name or f["name"])
                if not settings.dry_run:
                    drive.move(f["id"], inbox_id, dest, new_name,
                               {STATUS_KEY: "routed", "sr_category": result.category,
                                "sr_similarity": f"{result.similarity:.3f}"})
                summary["moved"] += 1
            entry["duration_ms"] = int((time.monotonic() - t0) * 1000)
            log.info("file classified", extra=entry)
            summary["files"].append(entry)
        except Exception as exc:
            summary["errors"] += 1
            log.exception("file failed", extra={"file_id": f["id"], "file_name": f["name"], "error": str(exc)})
            summary["files"].append({"file_id": f["id"], "file_name": f["name"], "action": "error", "error": str(exc)})

    summary["duration_ms"] = int((time.monotonic() - started) * 1000)
    log.info("sync finished", extra={k: v for k, v in summary.items() if k != "files"})
    return summary


# ── App ────────────────────────────────────────────────────────────────────────────────────────


class Runtime:
    """Process-wide state: one model, one Drive client, one sync at a time."""

    def __init__(self):
        self.settings = Settings()
        self.classifier = None
        self.drive = None
        self.lock = threading.Lock()
        self.last_run: dict | None = None

    def run(self, force: bool = False, dry_run: bool | None = None) -> dict | None:
        if not self.lock.acquire(blocking=False):
            return None  # a sync is already running
        try:
            if self.drive is None:
                self.drive = DriveClient(build_drive_service(), self.settings)
            settings = self.settings
            if dry_run is not None and dry_run != settings.dry_run:
                settings = Settings(**{**vars(settings), "dry_run": dry_run})
            self.last_run = {"at": datetime.now(timezone.utc).isoformat(),
                             **sync_once(self.drive, self.classifier, settings, force=force)}
            return self.last_run
        finally:
            self.lock.release()


runtime = Runtime()


def _scheduled_sync() -> None:
    try:
        runtime.run()
    except Exception:
        log.exception("scheduled sync failed")


@asynccontextmanager
async def lifespan(app: FastAPI):
    setup_logging()
    load_secrets_from_key_vault()
    runtime.settings = Settings()
    if runtime.classifier is None:  # tests inject their own
        runtime.classifier = SemanticClassifier(SentenceTransformerEmbedder(os.getenv("EMBEDDING_MODEL", DEFAULT_MODEL)))
    scheduler = None
    if runtime.settings.interval_min > 0:
        from apscheduler.schedulers.background import BackgroundScheduler

        scheduler = BackgroundScheduler(timezone="UTC")
        scheduler.add_job(_scheduled_sync, "interval", minutes=runtime.settings.interval_min,
                          max_instances=1, coalesce=True, id="drive-sync")
        scheduler.start()
    log.info("service started", extra={"dry_run": runtime.settings.dry_run,
                                       "interval_min": runtime.settings.interval_min})
    yield
    if scheduler:
        scheduler.shutdown(wait=False)


app = FastAPI(title="Drive Semantic Router", lifespan=lifespan)


@app.get("/health")
def health() -> dict:
    return {"status": "ok", "model_loaded": runtime.classifier is not None,
            "dry_run": runtime.settings.dry_run, "last_run": runtime.last_run and
            {k: v for k, v in runtime.last_run.items() if k != "files"}}


@app.post("/sync-documents")
def sync_documents(force: bool = False, dry_run: bool | None = None,
                   x_api_key: str | None = Header(default=None)) -> dict:
    expected = os.getenv("SYNC_API_KEY")
    if not expected:
        raise HTTPException(503, "SYNC_API_KEY not configured")
    if not x_api_key or not hmac.compare_digest(x_api_key, expected):
        raise HTTPException(401, "invalid API key")
    try:
        result = runtime.run(force=force, dry_run=dry_run)
    except Exception as exc:
        log.exception("manual sync failed")
        raise HTTPException(502, f"sync failed: {type(exc).__name__}") from exc
    if result is None:
        raise HTTPException(409, "a sync is already running")
    return result
