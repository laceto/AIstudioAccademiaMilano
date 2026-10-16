"""Google Calendar provider. Only ever called from an approved proposal."""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any
from zoneinfo import ZoneInfo

from ..config import AccountConfig

DEFAULT_DURATION = timedelta(hours=1)


def _is_date_only(s: str) -> bool:
    return len(s) == 10


def event_body(item: dict, tz: str) -> dict:
    """Proposal -> Google event resource. A bare date is all-day; a missing end is start + 1h."""
    start = item["start"]
    if _is_date_only(start):
        end = item.get("end") or (datetime.fromisoformat(start) + timedelta(days=1)).date().isoformat()
        when = {"start": {"date": start}, "end": {"date": end}}
    else:
        s = datetime.fromisoformat(start)
        if s.tzinfo is None:
            s = s.replace(tzinfo=ZoneInfo(tz))
        e = datetime.fromisoformat(item["end"]) if item.get("end") else s + DEFAULT_DURATION
        if e.tzinfo is None:
            e = e.replace(tzinfo=ZoneInfo(tz))
        when = {"start": {"dateTime": s.isoformat(), "timeZone": tz}, "end": {"dateTime": e.isoformat(), "timeZone": tz}}
    desc = f"Created from email: {item.get('source_subject', '')}\n{item.get('source_link', '')}".strip()
    body = {"summary": item["title"], "description": desc, **when}
    if item.get("location"):
        body["location"] = item["location"]
    return body


class GoogleCalendarProvider:
    def __init__(self, cfg: AccountConfig, service: Any | None = None):
        self.cfg, self._service = cfg, service

    @property
    def service(self) -> Any:
        if self._service is None:
            from .google_auth import build_service

            self._service = build_service(self.cfg, "calendar", "v3")
        return self._service

    def find_conflicts(self, start: str, end: str) -> list[dict]:
        res = self.service.events().list(
            calendarId="primary", timeMin=start, timeMax=end, singleEvents=True, maxResults=10
        ).execute()
        return res.get("items", [])

    def create_event(self, item: dict) -> str:
        body = event_body(item, self.cfg.timezone)
        return self.service.events().insert(calendarId="primary", body=body).execute()["id"]
