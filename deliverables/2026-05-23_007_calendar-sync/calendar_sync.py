"""
calendar_sync.py — Create events in Google Calendar, Outlook, and Apple iCloud.
All credentials via environment variables — never hardcoded.
"""

import os
from dataclasses import dataclass
from typing import Optional


@dataclass
class SyncResult:
    provider: str
    status: str          # "ok" | "error" | "skipped"
    link: Optional[str] = None
    error: Optional[str] = None


def create_google_event(event) -> SyncResult:
    """Env: GOOGLE_CREDENTIALS_JSON, GOOGLE_TOKEN_JSON"""
    try:
        from google.oauth2.credentials import Credentials
        from google.auth.transport.requests import Request
        from google_auth_oauthlib.flow import InstalledAppFlow
        from googleapiclient.discovery import build
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
                creds = InstalledAppFlow.from_client_secrets_file(creds_file, SCOPES).run_local_server(port=0)
            open(token_file, "w").write(creds.to_json())
        service = build("calendar", "v3", credentials=creds)
        body = {"summary": event.title, "location": event.location or "",
                "start": {"dateTime": f"{event.date}T{event.start_time}:00", "timeZone": event.timezone},
                "end":   {"dateTime": f"{event.date}T{event.end_time}:00",   "timeZone": event.timezone}}
        result = service.events().insert(calendarId="primary", body=body).execute()
        return SyncResult("Google Calendar", "ok", result.get("htmlLink"))
    except Exception as e:
        return SyncResult("Google Calendar", "error", error=str(e))


def create_outlook_event(event) -> SyncResult:
    """Env: MS_CLIENT_ID, MS_TENANT_ID (or OUTLOOK_ACCESS_TOKEN)"""
    try:
        import requests, time
        token = os.environ.get("OUTLOOK_ACCESS_TOKEN")
        if not token:
            cid = os.environ["MS_CLIENT_ID"]; tenant = os.environ.get("MS_TENANT_ID", "common")
            scope = "https://graph.microsoft.com/Calendars.ReadWrite offline_access"
            r = requests.post(f"https://login.microsoftonline.com/{tenant}/oauth2/v2.0/devicecode", data={"client_id": cid, "scope": scope})
            r.raise_for_status(); data = r.json()
            print(f"[Outlook] Open: {data['verification_uri']}  Code: {data['user_code']}")
            while True:
                time.sleep(data.get("interval", 5))
                t = requests.post(f"https://login.microsoftonline.com/{tenant}/oauth2/v2.0/token",
                                  data={"grant_type": "urn:ietf:params:oauth:grant-type:device_code", "client_id": cid, "device_code": data["device_code"]}).json()
                if "access_token" in t: token = t["access_token"]; break
                if t.get("error") not in ("authorization_pending", "slow_down"): raise RuntimeError(t)
        headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
        body = {"subject": event.title,
                "start": {"dateTime": f"{event.date}T{event.start_time}:00", "timeZone": event.timezone},
                "end":   {"dateTime": f"{event.date}T{event.end_time}:00",   "timeZone": event.timezone},
                "location": {"displayName": event.location or ""}}
        resp = requests.post("https://graph.microsoft.com/v1.0/me/events", headers=headers, json=body)
        resp.raise_for_status()
        return SyncResult("Outlook", "ok", resp.json().get("webLink"))
    except Exception as e:
        return SyncResult("Outlook", "error", error=str(e))


def create_apple_event(event) -> SyncResult:
    """Env: APPLE_ICLOUD_USERNAME, APPLE_APP_PASSWORD (app-specific password only)"""
    try:
        import caldav, uuid
        from icalendar import Calendar, Event as ICalEvent
        from datetime import datetime
        client = caldav.DAVClient(url="https://caldav.icloud.com",
                                  username=os.environ["APPLE_ICLOUD_USERNAME"],
                                  password=os.environ["APPLE_APP_PASSWORD"])
        cal = Calendar(); cal.add("prodid", "-//AI Studio//EN"); cal.add("version", "2.0")
        ev = ICalEvent()
        ev.add("uid", str(uuid.uuid4()))
        ev.add("summary", event.title)
        ev.add("dtstart", datetime.fromisoformat(f"{event.date}T{event.start_time}:00"))
        ev.add("dtend",   datetime.fromisoformat(f"{event.date}T{event.end_time}:00"))
        if event.location: ev.add("location", event.location)
        cal.add_component(ev)
        client.principal().calendars()[0].save_event(cal.to_ical())
        return SyncResult("Apple Calendar", "ok")
    except Exception as e:
        return SyncResult("Apple Calendar", "error", error=str(e))


def sync_to_all_calendars(event) -> list[SyncResult]:
    results = []
    results.append(create_google_event(event) if os.environ.get("GOOGLE_CREDENTIALS_JSON") or os.environ.get("GOOGLE_TOKEN_JSON")
                   else SyncResult("Google Calendar", "skipped", error="GOOGLE_CREDENTIALS_JSON not set"))
    results.append(create_outlook_event(event) if os.environ.get("MS_CLIENT_ID") or os.environ.get("OUTLOOK_ACCESS_TOKEN")
                   else SyncResult("Outlook", "skipped", error="MS_CLIENT_ID not set"))
    results.append(create_apple_event(event) if os.environ.get("APPLE_ICLOUD_USERNAME")
                   else SyncResult("Apple Calendar", "skipped", error="APPLE_ICLOUD_USERNAME not set"))
    return results
