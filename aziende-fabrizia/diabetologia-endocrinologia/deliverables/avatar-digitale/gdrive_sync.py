"""
Google Drive sync — salva digest e chat organizzati nella cartella Drive di Fabrizia.
Usa google-api-python-client con OAuth2.

Setup:
  1. Google Cloud Console → abilita Drive API
  2. Crea credenziali OAuth2 desktop → scarica credentials.json
  3. Prima run: apre browser per autorizzazione → salva token.json (locale, mai committare)
"""
import os
import io
from datetime import datetime
from pathlib import Path

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseUpload

SCOPES = ["https://www.googleapis.com/auth/drive.file"]

CREDS_FILE = os.getenv("GDRIVE_CREDENTIALS_PATH", "credentials.json")
TOKEN_FILE  = os.getenv("GDRIVE_TOKEN_PATH",       "token.json")

# Struttura cartelle su Drive
DRIVE_ROOT         = "Fabrizia — Avatar Digitale"
DRIVE_DIGESTS      = "Digest Giornalieri"
DRIVE_COMMUNITY    = "Community Snapshots"
DRIVE_DRAFT_POSTS  = "Bozze Post"


def _get_service():
    creds = None
    if Path(TOKEN_FILE).exists():
        creds = Credentials.from_authorized_user_file(TOKEN_FILE, SCOPES)
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file(CREDS_FILE, SCOPES)
            creds = flow.run_local_server(port=0)
        with open(TOKEN_FILE, "w") as f:
            f.write(creds.to_json())
    return build("drive", "v3", credentials=creds)


def _get_or_create_folder(service, name: str, parent_id: str | None = None) -> str:
    """Ottiene l'ID di una cartella Drive, la crea se non esiste."""
    q = f"name='{name}' and mimeType='application/vnd.google-apps.folder' and trashed=false"
    if parent_id:
        q += f" and '{parent_id}' in parents"

    results = service.files().list(q=q, fields="files(id,name)").execute()
    files = results.get("files", [])
    if files:
        return files[0]["id"]

    meta = {
        "name": name,
        "mimeType": "application/vnd.google-apps.folder",
    }
    if parent_id:
        meta["parents"] = [parent_id]
    folder = service.files().create(body=meta, fields="id").execute()
    return folder["id"]


def _ensure_folder_structure(service) -> dict[str, str]:
    """Crea/verifica struttura cartelle di Fabrizia su Drive."""
    root_id     = _get_or_create_folder(service, DRIVE_ROOT)
    digests_id  = _get_or_create_folder(service, DRIVE_DIGESTS,   root_id)
    community_id= _get_or_create_folder(service, DRIVE_COMMUNITY, root_id)
    drafts_id   = _get_or_create_folder(service, DRIVE_DRAFT_POSTS, root_id)
    return {
        "root":      root_id,
        "digests":   digests_id,
        "community": community_id,
        "drafts":    drafts_id,
    }


def upload_text_file(
    content: str,
    filename: str,
    folder_key: str = "digests",
    mime_type: str = "text/plain",
) -> str:
    """
    Carica un file di testo su Drive.
    Restituisce il link al file.
    folder_key: 'digests' | 'community' | 'drafts'
    """
    service = _get_service()
    folders = _ensure_folder_structure(service)
    folder_id = folders.get(folder_key, folders["digests"])

    file_meta = {
        "name":    filename,
        "parents": [folder_id],
    }
    media = MediaIoBaseUpload(
        io.BytesIO(content.encode("utf-8")),
        mimetype=mime_type,
        resumable=False,
    )
    file = service.files().create(
        body=file_meta,
        media_body=media,
        fields="id,webViewLink",
    ).execute()
    return file.get("webViewLink", "")


def save_daily_digest(digest_markdown: str, date_str: str = "") -> str:
    """Salva il digest giornaliero su Drive. Restituisce il link."""
    if not date_str:
        date_str = datetime.now().strftime("%Y-%m-%d")
    filename = f"Digest_{date_str}.md"
    return upload_text_file(digest_markdown, filename, folder_key="digests")


def save_community_snapshot(snapshot_json: str, group_name: str) -> str:
    """Salva uno snapshot di un gruppo community su Drive."""
    date_str = datetime.now().strftime("%Y-%m-%d_%H%M")
    safe_name = group_name.replace(" ", "_").replace("/", "-")[:40]
    filename = f"Snapshot_{date_str}_{safe_name}.json"
    return upload_text_file(
        snapshot_json, filename,
        folder_key="community",
        mime_type="application/json",
    )


def save_draft_post(draft_text: str, platform: str, topic_slug: str) -> str:
    """Salva una bozza post (LinkedIn, Telegram) su Drive."""
    date_str = datetime.now().strftime("%Y-%m-%d")
    filename = f"Draft_{platform}_{date_str}_{topic_slug[:30]}.md"
    return upload_text_file(draft_text, filename, folder_key="drafts")
