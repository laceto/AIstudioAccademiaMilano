"""Models: the boundary that stops malformed events from reaching Google."""

from __future__ import annotations

from datetime import datetime
from zoneinfo import ZoneInfo

import pytest
from pydantic import ValidationError

from deepagents_gcal.errors import TimeParseError
from deepagents_gcal.models import CalendarRef, Event, EventDraft, EventTime, FreeSlot

TZ = "Europe/Rome"
REF = datetime(2026, 9, 16, 9, 0, tzinfo=ZoneInfo(TZ))


def test_calendar_ref_from_api():
    ref = CalendarRef.from_api(
        {"id": "primary", "summary": "Luigi", "timeZone": "Europe/Rome", "primary": True}
    )
    assert (ref.id, ref.time_zone, ref.primary) == ("primary", "Europe/Rome", True)


def test_event_time_requires_exactly_one_representation():
    with pytest.raises(ValidationError):
        EventTime()
    with pytest.raises(ValidationError):
        EventTime(date="2026-09-17", date_time=REF)


def test_event_time_all_day_roundtrip():
    parsed = EventTime.from_api({"date": "2026-09-17"})
    assert parsed.all_day
    assert parsed.to_api() == {"date": "2026-09-17"}


def test_event_from_api_extracts_attendee_emails():
    event = Event.from_api(
        {
            "id": "evt_2",
            "summary": "Acme review",
            "start": {"dateTime": "2026-09-17T14:00:00+02:00", "timeZone": TZ},
            "end": {"dateTime": "2026-09-17T15:00:00+02:00", "timeZone": TZ},
            "attendees": [{"email": "mario@acme.it"}, {"displayName": "no email"}],
            "organizer": {"email": "luigi@studio.it"},
        }
    )
    assert event.attendees == ["mario@acme.it"]
    assert event.organizer == "luigi@studio.it"


def test_to_summary_drops_empty_and_default_fields():
    summary = Event.from_api(
        {
            "id": "evt_1",
            "summary": "Standup",
            "start": {"dateTime": "2026-09-17T09:00:00+02:00"},
            "end": {"dateTime": "2026-09-17T09:15:00+02:00"},
            "status": "confirmed",
        }
    ).to_summary()
    assert set(summary) == {"id", "summary", "start", "end"}


def test_draft_needs_end_or_duration():
    with pytest.raises(ValidationError):
        EventDraft(summary="Call", start="2026-09-17T10:00")


def test_draft_duration_produces_end():
    start, end, tz = EventDraft(
        summary="Call", start="2026-09-17T10:00", duration_minutes=45
    ).resolve(TZ)
    assert (end - start).total_seconds() == 45 * 60
    assert tz == TZ


def test_draft_rejects_end_before_start():
    draft = EventDraft(summary="Call", start="2026-09-17T10:00", end="2026-09-17T09:00")
    with pytest.raises(TimeParseError):
        draft.resolve(TZ)


def test_draft_rejects_zero_length_events():
    draft = EventDraft(summary="Call", start="2026-09-17T10:00", end="2026-09-17T10:00")
    with pytest.raises(TimeParseError):
        draft.resolve(TZ)


def test_draft_rejects_malformed_attendee():
    with pytest.raises(ValidationError):
        EventDraft(summary="Call", start="now", duration_minutes=30, attendees=["not-an-email"])


def test_draft_rejects_unknown_fields():
    with pytest.raises(ValidationError):
        EventDraft(summary="Call", start="now", duration_minutes=30, calendar_id="primary")


def test_draft_to_api_timed_event():
    body = EventDraft(
        summary="Acme review",
        start="2026-09-17T14:00",
        duration_minutes=60,
        location="Milano",
        attendees=["mario@acme.it"],
        reminders_minutes=[10],
    ).to_api(TZ)
    assert body["summary"] == "Acme review"
    assert body["start"]["timeZone"] == TZ
    assert body["end"]["dateTime"].startswith("2026-09-17T15:00")
    assert body["attendees"] == [{"email": "mario@acme.it"}]
    assert body["reminders"] == {
        "useDefault": False,
        "overrides": [{"method": "popup", "minutes": 10}],
    }


def test_draft_to_api_all_day_uses_date_blocks():
    body = EventDraft(summary="Ferie", start="2026-09-17", end="2026-09-18", all_day=True).to_api(TZ)
    assert body["start"] == {"date": "2026-09-17"}
    assert body["end"] == {"date": "2026-09-18"}


def test_draft_relative_start_resolves_against_reference():
    start, end, _ = EventDraft(summary="Sync", start="+2h", duration_minutes=30).resolve(
        TZ, reference=REF
    )
    assert start.hour == 11 and end.hour == 11 and end.minute == 30


def test_free_slot_duration():
    slot = FreeSlot(
        start=datetime(2026, 9, 17, 9, tzinfo=ZoneInfo(TZ)),
        end=datetime(2026, 9, 17, 10, 30, tzinfo=ZoneInfo(TZ)),
    )
    assert slot.duration_minutes == 90
    assert slot.to_summary()["duration_minutes"] == 90
