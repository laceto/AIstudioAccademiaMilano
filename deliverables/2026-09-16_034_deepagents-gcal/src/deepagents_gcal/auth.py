"""Credential loading for the Google Calendar API.

Three ways in, checked in this order:

1. `GCAL_TOKEN_JSON` — the authorised-user token as inline JSON (containers).
2. A service-account key file, optionally impersonating `subject`.
3. The installed-app OAuth flow, caching a token file on disk.

Google's client libraries are imported lazily so the rest of the package (models,
tool schemas, planning logic) stays importable — and testable — without them.
"""

from __future__ import annotations

import json
import os
from typing import Any

from .config import TOKEN_JSON_ENV, CalendarSettings
from .errors import AuthError

SCOPE_READONLY = "https://www.googleapis.com/auth/calendar.readonly"
SCOPE_EVENTS = "https://www.googleapis.com/auth/calendar.events"


def scopes_for(read_only: bool) -> list[str]:
    """Least-privilege scope set for the requested access level."""
    return [SCOPE_READONLY] if read_only else [SCOPE_READONLY, SCOPE_EVENTS]


def _require_google() -> tuple[Any, Any, Any]:
    try:
        from google.auth.transport.requests import Request
        from google.oauth2.credentials import Credentials
        from googleapiclient.discovery import build
    except ImportError as exc:  # pragma: no cover - depends on the install extras
        raise AuthError(
            "Google client libraries are missing. Install them with "
            "`pip install deepagents-gcal` (they are a hard dependency) or "
            "`pip install google-api-python-client google-auth google-auth-oauthlib`."
        ) from exc
    return Credentials, Request, build


def load_credentials(settings: CalendarSettings, *, allow_interactive: bool = False) -> Any:
    """Return usable Google credentials, or raise `AuthError` with a fix-it message.

    `allow_interactive` gates the browser-based OAuth consent flow. It is off by
    default so an agent running headless fails loudly instead of hanging on a
    localhost redirect that nobody will ever open.
    """
    Credentials, Request, _ = _require_google()
    scopes = scopes_for(settings.read_only)

    inline_token = os.environ.get(TOKEN_JSON_ENV)
    if inline_token:
        try:
            info = json.loads(inline_token)
        except json.JSONDecodeError as exc:
            raise AuthError(f"{TOKEN_JSON_ENV} is not valid JSON") from exc
        creds = Credentials.from_authorized_user_info(info, scopes)
        return _refreshed(creds, Request)

    if settings.service_account_file:
        return _service_account_credentials(settings, scopes)

    if os.path.exists(settings.token_file):
        creds = Credentials.from_authorized_user_file(settings.token_file, scopes)
        creds = _refreshed(creds, Request)
        if creds and creds.valid:
            _persist(creds, settings.token_file)
            return creds

    if not allow_interactive:
        raise AuthError(
            f"No usable token at {settings.token_file!r}. Run `deepagents-gcal auth` once "
            f"(or set {TOKEN_JSON_ENV}) before starting the agent."
        )

    return _run_installed_flow(settings, scopes)


def _refreshed(creds: Any, Request: Any) -> Any:
    if creds and creds.expired and creds.refresh_token:
        try:
            creds.refresh(Request())
        except Exception as exc:  # noqa: BLE001 - surfaced as AuthError with guidance
            raise AuthError(f"Token refresh failed: {exc}. Re-run `deepagents-gcal auth`.") from exc
    return creds


def _service_account_credentials(settings: CalendarSettings, scopes: list[str]) -> Any:
    try:
        from google.oauth2 import service_account
    except ImportError as exc:  # pragma: no cover
        raise AuthError("google-auth is required for service-account authentication") from exc
    if not os.path.exists(settings.service_account_file or ""):
        raise AuthError(f"Service-account key not found: {settings.service_account_file}")
    creds = service_account.Credentials.from_service_account_file(
        settings.service_account_file, scopes=scopes
    )
    if settings.subject:
        creds = creds.with_subject(settings.subject)
    return creds


def _run_installed_flow(settings: CalendarSettings, scopes: list[str]) -> Any:
    try:
        from google_auth_oauthlib.flow import InstalledAppFlow
    except ImportError as exc:  # pragma: no cover
        raise AuthError("google-auth-oauthlib is required for the OAuth consent flow") from exc
    if not os.path.exists(settings.credentials_file):
        raise AuthError(
            f"OAuth client secrets not found at {settings.credentials_file!r}. Download them from "
            "Google Cloud Console → APIs & Services → Credentials → OAuth client ID (Desktop app)."
        )
    flow = InstalledAppFlow.from_client_secrets_file(settings.credentials_file, scopes)
    creds = flow.run_local_server(port=0)
    _persist(creds, settings.token_file)
    return creds


def _persist(creds: Any, token_file: str) -> None:
    """Write the token with owner-only permissions; never echo its contents."""
    directory = os.path.dirname(os.path.abspath(token_file))
    os.makedirs(directory, exist_ok=True)
    with open(token_file, "w", encoding="utf-8") as handle:
        handle.write(creds.to_json())
    try:
        os.chmod(token_file, 0o600)
    except OSError:  # pragma: no cover - non-POSIX filesystems
        pass


def build_service(settings: CalendarSettings, credentials: Any | None = None) -> Any:
    """Build the `calendar` v3 service object."""
    _, _, build = _require_google()
    creds = credentials or load_credentials(settings)
    return build("calendar", "v3", credentials=creds, cache_discovery=False)
