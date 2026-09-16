"""Shared fakes: a stand-in for the googleapiclient `calendar` v3 service.

The fake mirrors the chained-builder shape of the real client
(`service.events().list(**params).execute()`), so the production code path is
exercised end to end without a network call or a credential.
"""

from __future__ import annotations

from typing import Any

import pytest

from deepagents_gcal.client import GoogleCalendarClient
from deepagents_gcal.config import CalendarSettings


class FakeHttpError(Exception):
    """Mimics googleapiclient.errors.HttpError enough for the client's translation."""

    def __init__(self, status: int, message: str = "boom") -> None:
        super().__init__(message)
        self.resp = type("Resp", (), {"status": status})()


class _Request:
    def __init__(self, result: Any, error: Exception | None = None) -> None:
        self._result, self._error = result, error

    def execute(self) -> Any:
        if self._error:
            raise self._error
        return self._result


class FakeCalendarService:
    """In-memory Google Calendar. Records every call for assertions."""

    def __init__(
        self,
        events: list[dict[str, Any]] | None = None,
        calendars: list[dict[str, Any]] | None = None,
        busy: list[dict[str, str]] | None = None,
        errors: dict[str, Exception] | None = None,
        freebusy_errors: dict[str, list[dict[str, str]]] | None = None,
        page_size: int | None = None,
    ) -> None:
        self.stored_events = {e["id"]: e for e in (events or [])}
        self.calendars = calendars or [
            {"id": "primary", "summary": "Luigi", "timeZone": "Europe/Rome",
             "accessRole": "owner", "primary": True},
            {"id": "team@studio.it", "summary": "Studio", "accessRole": "writer"},
        ]
        self.busy = busy or []
        self.errors = errors or {}
        self.freebusy_errors = freebusy_errors or {}
        self.page_size = page_size  # when set, events.list paginates like the real API
        self.calls: list[tuple[str, dict[str, Any]]] = []

    def _record(self, name: str, params: dict[str, Any]) -> None:
        self.calls.append((name, params))

    def calendarList(self) -> Any:
        outer = self

        class _CalendarList:
            def list(self, **params: Any) -> _Request:
                outer._record("calendarList.list", params)
                return _Request({"items": outer.calendars}, outer.errors.get("calendarList.list"))

        return _CalendarList()

    def events(self) -> Any:
        outer = self

        class _Events:
            def list(self, **params: Any) -> _Request:
                outer._record("events.list", params)
                items = list(outer.stored_events.values())
                query = params.get("q")
                if query:
                    items = [e for e in items if query.lower() in e.get("summary", "").lower()]
                if outer.page_size is None:
                    return _Request({"items": items}, outer.errors.get("events.list"))
                offset = int(params.get("pageToken") or 0)
                page = items[offset : offset + outer.page_size]
                payload: dict[str, Any] = {"items": page}
                if offset + outer.page_size < len(items):
                    payload["nextPageToken"] = str(offset + outer.page_size)
                return _Request(payload, outer.errors.get("events.list"))

            def get(self, **params: Any) -> _Request:
                outer._record("events.get", params)
                event = outer.stored_events.get(params["eventId"])
                error = outer.errors.get("events.get")
                if event is None and error is None:
                    error = FakeHttpError(404)
                return _Request(event, error)

            def insert(self, **params: Any) -> _Request:
                outer._record("events.insert", params)
                body = dict(params["body"])
                body.setdefault("id", "evt_new")
                body["htmlLink"] = "https://calendar.google.com/event?eid=evt_new"
                outer.stored_events[body["id"]] = body
                return _Request(body, outer.errors.get("events.insert"))

            def patch(self, **params: Any) -> _Request:
                outer._record("events.patch", params)
                current = dict(outer.stored_events.get(params["eventId"], {"id": params["eventId"]}))
                current.update(params["body"])
                outer.stored_events[params["eventId"]] = current
                return _Request(current, outer.errors.get("events.patch"))

            def delete(self, **params: Any) -> _Request:
                outer._record("events.delete", params)
                outer.stored_events.pop(params["eventId"], None)
                return _Request("", outer.errors.get("events.delete"))

        return _Events()

    def freebusy(self) -> Any:
        outer = self

        class _FreeBusy:
            def query(self, body: dict[str, Any]) -> _Request:
                outer._record("freebusy.query", body)
                calendars: dict[str, Any] = {}
                for item in body["items"]:
                    cid = item["id"]
                    if cid in outer.freebusy_errors:
                        calendars[cid] = {"busy": [], "errors": outer.freebusy_errors[cid]}
                    else:
                        calendars[cid] = {"busy": outer.busy}
                return _Request({"calendars": calendars}, outer.errors.get("freebusy.query"))

        return _FreeBusy()


def api_event(
    event_id: str,
    summary: str,
    start: str,
    end: str,
    **extra: Any,
) -> dict[str, Any]:
    """Build a Google-shaped timed event payload."""
    return {
        "id": event_id,
        "summary": summary,
        "start": {"dateTime": start, "timeZone": "Europe/Rome"},
        "end": {"dateTime": end, "timeZone": "Europe/Rome"},
        "status": "confirmed",
        **extra,
    }


@pytest.fixture
def fake_service() -> FakeCalendarService:
    return FakeCalendarService(
        events=[
            api_event("evt_1", "Standup", "2026-09-17T09:00:00+02:00", "2026-09-17T09:15:00+02:00"),
            api_event(
                "evt_2",
                "Acme review",
                "2026-09-17T14:00:00+02:00",
                "2026-09-17T15:00:00+02:00",
                location="Milano",
                attendees=[{"email": "mario@acme.it"}],
            ),
        ]
    )


@pytest.fixture
def settings() -> CalendarSettings:
    return CalendarSettings(timezone="Europe/Rome", calendar_id="primary")


@pytest.fixture
def client(fake_service: FakeCalendarService, settings: CalendarSettings) -> GoogleCalendarClient:
    return GoogleCalendarClient(service=fake_service, settings=settings)
