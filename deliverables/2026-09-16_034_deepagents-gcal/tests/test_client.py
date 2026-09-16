"""Client behaviour against a fake Google service — including the write guards."""

from __future__ import annotations

from datetime import datetime
from typing import Any
from zoneinfo import ZoneInfo

import pytest

from conftest import FakeCalendarService, FakeHttpError, api_event
from deepagents_gcal.client import GoogleCalendarClient
from deepagents_gcal.config import CalendarSettings
from deepagents_gcal.errors import (
    ApiError,
    CalendarNotAllowedError,
    EventNotFoundError,
    ReadOnlyError,
)
from deepagents_gcal.models import EventDraft

TZ = "Europe/Rome"
ZONE = ZoneInfo(TZ)


def test_list_calendars_maps_payloads(client):
    calendars = client.list_calendars()
    assert [c.id for c in calendars] == ["primary", "team@studio.it"]
    assert calendars[0].primary is True


def test_list_events_requests_expanded_ordered_results(client, fake_service):
    events = client.list_events(time_min="2026-09-17", time_max="2026-09-18")
    assert [e.summary for e in events] == ["Standup", "Acme review"]
    _, params = fake_service.calls[-1]
    assert params["singleEvents"] is True
    assert params["orderBy"] == "startTime"
    assert params["calendarId"] == "primary"
    assert params["timeMin"].startswith("2026-09-17T00:00")


def test_list_events_defaults_to_a_seven_day_window(client, fake_service):
    client.list_events()
    _, params = fake_service.calls[-1]
    start = datetime.fromisoformat(params["timeMin"])
    end = datetime.fromisoformat(params["timeMax"])
    assert (end - start).days == 7


def test_search_events_passes_the_query_through(client, fake_service):
    results = client.search_events("acme")
    assert [e.summary for e in results] == ["Acme review"]
    assert fake_service.calls[-1][1]["q"] == "acme"


def test_get_event_missing_id_raises_event_not_found(client):
    with pytest.raises(EventNotFoundError):
        client.get_event("nope")


def test_api_denial_becomes_api_error_with_status(settings):
    service = FakeCalendarService(errors={"events.list": FakeHttpError(403, "insufficient scope")})
    client = GoogleCalendarClient(service=service, settings=settings)
    with pytest.raises(ApiError) as excinfo:
        client.list_events()
    assert excinfo.value.status == 403
    assert "access denied" in str(excinfo.value).lower()


def test_create_event_sends_a_google_shaped_body(client, fake_service):
    event = client.create_event(
        EventDraft(summary="Sync", start="2026-09-18T10:00", duration_minutes=30)
    )
    _, params = fake_service.calls[-1]
    assert params["body"]["summary"] == "Sync"
    assert params["body"]["end"]["dateTime"].startswith("2026-09-18T10:30")
    assert params["sendUpdates"] == "none"
    assert event.html_link


def test_create_event_can_notify_attendees(client, fake_service):
    client.create_event(
        EventDraft(summary="Sync", start="2026-09-18T10:00", duration_minutes=30),
        send_updates="all",
    )
    assert fake_service.calls[-1][1]["sendUpdates"] == "all"


def test_update_event_patches_only_given_fields(client, fake_service):
    client.update_event("evt_1", {"summary": "Standup (moved)"})
    _, params = fake_service.calls[-1]
    assert params["body"] == {"summary": "Standup (moved)"}
    assert params["eventId"] == "evt_1"


def test_update_event_rejects_an_empty_change_set(client):
    with pytest.raises(ValueError):
        client.update_event("evt_1", {})


def test_delete_event_returns_a_receipt(client, fake_service):
    assert client.delete_event("evt_1") == {
        "deleted": True,
        "event_id": "evt_1",
        "calendar_id": "primary",
    }
    assert "evt_1" not in fake_service.stored_events


def test_read_only_client_refuses_every_write(fake_service):
    client = GoogleCalendarClient(
        service=fake_service, settings=CalendarSettings(read_only=True, timezone=TZ)
    )
    draft = EventDraft(summary="Sync", start="2026-09-18T10:00", duration_minutes=30)
    for call in (
        lambda: client.create_event(draft),
        lambda: client.update_event("evt_1", {"summary": "x"}),
        lambda: client.delete_event("evt_1"),
    ):
        with pytest.raises(ReadOnlyError):
            call()
    assert not [name for name, _ in fake_service.calls if name.startswith("events.")]


def test_dry_run_validates_but_never_calls_the_api(fake_service):
    client = GoogleCalendarClient(
        service=fake_service, settings=CalendarSettings(dry_run=True, timezone=TZ)
    )
    event = client.create_event(
        EventDraft(summary="Sync", start="2026-09-18T10:00", duration_minutes=30)
    )
    assert event.id == "dry-run"
    assert client.delete_event("evt_1")["dry_run"] is True
    assert "evt_1" in fake_service.stored_events
    assert not [name for name, _ in fake_service.calls if name in {"events.insert", "events.delete"}]


def test_dry_run_still_rejects_an_invalid_draft(fake_service):
    client = GoogleCalendarClient(
        service=fake_service, settings=CalendarSettings(dry_run=True, timezone=TZ)
    )
    with pytest.raises(Exception):
        client.create_event(
            EventDraft(summary="Sync", start="2026-09-18T11:00", end="2026-09-18T10:00")
        )


def test_busy_intervals_query_every_requested_calendar(client, fake_service):
    fake_service.busy = [
        {"start": "2026-09-17T10:00:00+02:00", "end": "2026-09-17T11:00:00+02:00"}
    ]
    intervals = client.busy_intervals(
        datetime(2026, 9, 17, tzinfo=ZONE),
        datetime(2026, 9, 18, tzinfo=ZONE),
        calendar_ids=["primary", "team@studio.it"],
    )
    body = fake_service.calls[-1][1]
    assert [item["id"] for item in body["items"]] == ["primary", "team@studio.it"]
    # one busy block per calendar in the fake
    assert len(intervals) == 2


def test_find_free_slots_uses_freebusy_and_working_hours(client, fake_service):
    fake_service.busy = [
        {"start": "2026-09-17T09:00:00+02:00", "end": "2026-09-17T12:00:00+02:00"}
    ]
    slots = client.find_free_slots(
        60, time_min="2026-09-17T00:00", time_max="2026-09-18T00:00", working_hours=(9, 18)
    )
    assert [(s.start.hour, s.end.hour) for s in slots] == [(12, 18)]


def test_client_from_env_reads_gcal_variables(monkeypatch):
    monkeypatch.setenv("GCAL_CALENDAR_ID", "team@studio.it")
    monkeypatch.setenv("GCAL_TIMEZONE", "Europe/Lisbon")
    monkeypatch.setenv("GCAL_READ_ONLY", "true")
    client = GoogleCalendarClient.from_env()
    assert client.settings.calendar_id == "team@studio.it"
    assert client.timezone == "Europe/Lisbon"
    assert client.settings.read_only is True


def test_explicit_calendar_id_overrides_the_default(client, fake_service):
    client.list_events(calendar_id="team@studio.it")
    assert fake_service.calls[-1][1]["calendarId"] == "team@studio.it"


def test_event_payload_without_attendees_is_handled(client, fake_service):
    fake_service.stored_events["evt_3"] = api_event(
        "evt_3", "Solo", "2026-09-17T16:00:00+02:00", "2026-09-17T16:30:00+02:00"
    )
    assert client.get_event("evt_3").attendees == []


def test_cancelled_recurring_instances_are_skipped(client, fake_service):
    fake_service.stored_events["evt_cancelled"] = {"id": "evt_cancelled", "status": "cancelled"}
    events = client.list_events(time_min="2026-09-17", time_max="2026-09-18")
    assert [e.id for e in events] == ["evt_1", "evt_2"]


def test_allowlist_is_a_boundary_not_a_default(fake_service):
    """Google has no per-calendar scope, so this is the only containment there is."""
    client = GoogleCalendarClient(
        service=fake_service,
        settings=CalendarSettings(
            calendar_id="team@studio.it", allowed_calendar_ids=["team@studio.it"], timezone=TZ
        ),
    )
    assert client.list_events(calendar_id="team@studio.it") is not None
    for call in (
        lambda: client.list_events(calendar_id="primary"),
        lambda: client.get_event("evt_1", calendar_id="primary"),
        lambda: client.create_event(
            EventDraft(summary="x", start="2026-09-18T10:00", duration_minutes=30),
            calendar_id="primary",
        ),
        lambda: client.delete_event("evt_1", calendar_id="primary"),
    ):
        with pytest.raises(CalendarNotAllowedError):
            call()


def test_allowlist_covers_multi_calendar_freebusy(fake_service):
    client = GoogleCalendarClient(
        service=fake_service,
        settings=CalendarSettings(
            calendar_id="team@studio.it", allowed_calendar_ids=["team@studio.it"], timezone=TZ
        ),
    )
    with pytest.raises(CalendarNotAllowedError):
        client.find_free_slots(60, calendar_ids=["team@studio.it", "someone-else@acme.it"])


def test_settings_reject_a_default_calendar_outside_its_own_allowlist():
    with pytest.raises(ValueError):
        CalendarSettings(calendar_id="primary", allowed_calendar_ids=["team@studio.it"])


def test_unreadable_calendar_raises_instead_of_reporting_it_free(settings):
    service = FakeCalendarService(freebusy_errors={"typo@acme.it": [{"reason": "notFound"}]})
    client = GoogleCalendarClient(service=service, settings=settings)
    with pytest.raises(ApiError) as excinfo:
        client.find_free_slots(60, calendar_ids=["typo@acme.it"])
    assert "notFound" in str(excinfo.value)


def test_listing_follows_pagination_up_to_the_cap(settings):
    events = [
        api_event(f"evt_{i}", f"Event {i}", "2026-09-17T09:00:00+02:00", "2026-09-17T09:30:00+02:00")
        for i in range(7)
    ]
    service = FakeCalendarService(events=events, page_size=3)
    client = GoogleCalendarClient(service=service, settings=settings)

    assert len(client.list_events(max_results=7)) == 7
    assert len([c for c, _ in service.calls if c == "events.list"]) == 3
    assert len(client.list_events(max_results=2)) == 2


def test_get_event_on_a_cancelled_instance_is_a_calendar_error(client, fake_service):
    fake_service.stored_events["evt_cancelled"] = {"id": "evt_cancelled", "status": "cancelled"}
    with pytest.raises(EventNotFoundError):
        client.get_event("evt_cancelled")


def test_google_error_bodies_are_truncated_before_they_reach_callers(settings):
    service = FakeCalendarService(errors={"events.list": FakeHttpError(500, "x" * 2000)})
    client = GoogleCalendarClient(service=service, settings=settings)
    with pytest.raises(ApiError) as excinfo:
        client.list_events()
    assert len(str(excinfo.value)) < 500


def test_retries_are_requested_when_the_service_supports_them(settings):
    seen: dict[str, Any] = {}

    class RetryAwareService(FakeCalendarService):
        def calendarList(self):
            outer = self

            class _CalendarList:
                def list(self, **params):
                    class _R:
                        def execute(self, num_retries=0):
                            seen["num_retries"] = num_retries
                            return {"items": outer.calendars}

                    return _R()

            return _CalendarList()

    client = GoogleCalendarClient(
        service=RetryAwareService(), settings=settings.model_copy(update={"max_retries": 3})
    )
    client.list_calendars()
    assert seen["num_retries"] == 3
