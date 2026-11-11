"""Read-only Google credentials. Token from env CALENDAR_SENTINEL_TOKEN (JSON) or a local file; never logged."""

from __future__ import annotations

import json
import os

SCOPES = ["https://www.googleapis.com/auth/calendar.readonly"]
TOKEN_FILE = os.environ.get("CALENDAR_SENTINEL_TOKEN_FILE", "credentials/calendar_sentinel_token.json")
CLIENT_FILE = os.environ.get("GOOGLE_CREDENTIALS_FILE", "credentials/google_credentials.json")


def interactive_auth() -> str:
    from google_auth_oauthlib.flow import InstalledAppFlow

    creds = InstalledAppFlow.from_client_secrets_file(CLIENT_FILE, SCOPES).run_local_server(port=0)
    os.makedirs(os.path.dirname(os.path.abspath(TOKEN_FILE)), exist_ok=True)
    fd = os.open(TOKEN_FILE, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(fd, "w", encoding="utf-8") as f:
        f.write(creds.to_json())
    return TOKEN_FILE


def build_service():
    from google.auth.transport.requests import Request
    from google.oauth2.credentials import Credentials
    from googleapiclient.discovery import build

    if os.environ.get("CALENDAR_SENTINEL_TOKEN"):
        creds = Credentials.from_authorized_user_info(json.loads(os.environ["CALENDAR_SENTINEL_TOKEN"]), SCOPES)
    elif os.path.exists(TOKEN_FILE):
        creds = Credentials.from_authorized_user_file(TOKEN_FILE, SCOPES)
    else:
        raise SystemExit("no token: run `python -m calendarsentinel auth` once")
    if creds.expired and creds.refresh_token:
        creds.refresh(Request())
    return build("calendar", "v3", credentials=creds, cache_discovery=False)
