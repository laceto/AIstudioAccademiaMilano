"""
calendar_sync.py — Create calendar events across Google, Outlook, and Apple.

Each provider is an independent adapter. All return a result dict:
    {"provider": str, "status": "ok"|"error", "link": str|None, "error": str|None}

Credentials are NEVER hardcoded. All sourced from environment variables.
"""

import os
from dataclasses import dataclass, field
from typing import Optional

from event_parser import CalendarEvent


@dataclass
class SyncResult:
    provider: str
    status: str          # "ok" | "error" | "skipped"
    link: Optional[str] = None
    error: Optional[str] = None


# ——— Google Calendar ——————————————————————————————————————————————

def create_google_event(event: CalendarEvent) -> SyncResult:
    """
    Requires env:
        GOOGLE_CREDENTIALS_JSON  — path to OAuth2 credentials.json from Google Cloud Console
        GOOGLE_TOKEN_JSON        — path to token.json (created on first auth run)
    """
    try:
        from google.oauth2.credentials import Credentials
        from google.auth.transport.requests import Request
        from google_auth_oauthlib.flow import InstalledAppFlow
        from googleapiclient.discovery import build
        import json

        SCOPES = ["https://www.googleapis.com/auth/calendar.events"]
        creds_file = os.environ.get("GOOGLE_CREDENTIALS_JSON", "credentials.json")
        token_file = os.environ.get("GOOGLE_TOKEN_JSON", "google_token.json")

        creds = None
        if os.path.exists(token_file):
            creds = Credentials.from_authorized_user_file(token_file, SCOPES)
        if not creds or not creds.valid:
            if creds and creds.expired and creds.refresh_token:
                creds.refresh(Request())
            else:
                flow = InstalledAppFlow.from_client_secrets_file(creds_file, SCOPES)
                creds = flow.run_local_server(port=0)
            with open(token_file, "w") as f:
                f.write(creds.to_json())

        service = build("calendar", "v3", credentials=creds)
        body = {
            "summary": event.title,
            "location": event.location or "",
            "description": event.description or "",
            "start": {"dateTime": f"{event.date}T{event.start_time}:00", "timeZone": event.timezone},
            "end":   {"dateTime": f"{event.date}T{event.end_time}:00",   "timeZone": event.timezone},
        }
        result = service.events().insert(calendarId="primary", body=body).execute()
        return SyncResult(provider="Google Calendar", status="ok", link=result.get("htmlLink"))

    except Exception as e:
        return SyncResult(provider="Google Calendar", status="error", error=str(e))


# ——— Microsoft Outlook (Graph API) ———————————————————————————————————————

def _get_outlook_token() -> str:
    """
    Device code flow — works headless (no browser redirect needed on server).
    Requires env: MS_CLIENT_ID, MS_TENANT_ID (or "common" for personal accounts)
    """
    import requests

    client_id = os.environ["MS_CLIENT_ID"]
    tenant    = os.environ.get("MS_TENANT_ID", "common")
    scope     = "https://graph.microsoft.com/Calendars.ReadWrite offline_access"

    # Step 1: request device code
    resp = requests.post(
        f"https://login.microsoftonline.com/{tenant}/oauth2/v2.0/devicecode",
        data={"client_id": client_id, "scope": scope},
    )
    resp.raise_for_status()
    data = resp.json()
    print(f"[Outlook] Open: {data['verification_uri']}  —  Code: {data['user_code']}")

    # Step 2: poll until user completes auth
    import time
    while True:
        time.sleep(data.get("interval", 5))
        token_resp = requests.post(
            f"https://login.microsoftonline.com/{tenant}/oauth2/v2.0/token",
            data={"grant_type": "urn:ietf:params:oauth:grant-type:device_code",
                  "client_id": client_id, "device_code": data["device_code"]},
        )
        t = token_resp.json()
        if "access_token" in t:
            return t["access_token"]
        if t.get("error") not in ("authorization_pending", "slow_down"):
            raise RuntimeError(f"Outlook auth failed: {t}")


def create_outlook_event(event: CalendarEvent) -> SyncResult:
    """
    Requires env: MS_CLIENT_ID, MS_TENANT_ID (or OUTLOOK_ACCESS_TOKEN for pre-authenticated)
    """
    try:
        import requests

        token = os.environ.get("OUTLOOK_ACCESS_TOKEN") or _get_outlook_token()
        headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
        body = {
            "subject": event.title,
            "start":    {"dateTime": f"{event.date}T{event.start_time}:00", "timeZone": event.timezone},
            "end":      {"dateTime": f"{event.date}T{event.end_time}:00",   "timeZone": event.timezone},
            "location": {"displayName": event.location or ""},
            "body":     {"contentType": "HTML", "content": event.description or ""},
        }
        resp = requests.post(
            "https://graph.microsoft.com/v1.0/me/events",
            headers=headers, json=body,
        )
        resp.raise_for_status()
        return SyncResult(provider="Outlook", status="ok", link=resp.json().get("webLink"))

    except Exception as e:
        return SyncResult(provider="Outlook", status="error", error=str(e))


# ——— Apple Calendar (iCloud CalDAV) ——————————————————————————————————————

def create_apple_event(event: CalendarEvent) -> SyncResult:
    """
    Uses iCloud CalDAV. Requires an app-specific password (NOT your Apple ID password).
    Generate at: https://appleid.apple.com → Security → App-specific passwords

    Requires env:
        APPLE_ICLOUD_USERNAME   — your Apple ID email
        APPLE_APP_PASSWORD      — app-specific password (never your main password)
    """
    try:
        import caldav
        from icalendar import Calendar, Event as ICalEvent
        from datetime import datetime
        import uuid

        username = os.environ["APPLE_ICLOUD_USERNAME"]
        password = os.environ["APPLE_APP_PASSWORD"]

        client = caldav.DAVClient(
            url="https://caldav.icloud.com",
            username=username,
            password=password,
        )
        principal = client.principal()
        calendars = principal.calendars()
        if not calendars:
            raise RuntimeError("No calendars found in iCloud account")
        calendar = calendars[0]  # primary calendar

        cal = Calendar()
        cal.add("prodid", "-//AI Studio Accademia Milano//CalSync//EN")
        cal.add("version", "2.0")

        ev = ICalEvent()
        ev.add("uid",     str(uuid.uuid4()))
        ev.add("summary", event.title)
        ev.add("dtstart", datetime.fromisoformat(f"{event.date}T{event.start_time}:00"))
        ev.add("dtend",   datetime.fromisoformat(f"{event.date}T{event.end_time}:00"))
        if event.location:
            ev.add("location", event.location)
        if event.description:
            ev.add("description", event.description)
        cal.add_component(ev)

        calendar.save_event(cal.to_ical())
        return SyncResult(provider="Apple Calendar", status="ok")

    except Exception as e:
        return SyncResult(provider="Apple Calendar", status="error", error=str(e))


# ——— Orchestrator ———————————————————————————————————————————————————

def sync_to_all_calendars(event: CalendarEvent) -> list[SyncResult]:
    results = []
    if os.environ.get("GOOGLE_CREDENTIALS_JSON") or os.environ.get("GOOGLE_TOKEN_JSON"):
        results.append(create_google_event(event))
    else:
        results.append(SyncResult(provider="Google Calendar", status="skipped", error="GOOGLE_CREDENTIALS_JSON not set"))

    if os.environ.get("MS_CLIENT_ID") or os.environ.get("OUTLOOK_ACCESS_TOKEN"):
        results.append(create_outlook_event(event))
    else:
        results.append(SyncResult(provider="Outlook", status="skipped", error="MS_CLIENT_ID not set"))

    if os.environ.get("APPLE_ICLOUD_USERNAME"):
        results.append(create_apple_event(event))
    else:
        results.append(SyncResult(provider="Apple Calendar", status="skipped", error="APPLE_ICLOUD_USERNAME not set"))

    return results
