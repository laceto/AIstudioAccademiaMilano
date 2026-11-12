"""Tool layer: schemas, JSON contract, and the read-only/write split."""

from __future__ import annotations

import json

import pytest

from deepagents_gcal.client import GoogleCalendarClient
from deepagents_gcal.config import CalendarSettings
from deepagents_gcal.tools import WRITE_TOOL_NAMES, build_calendar_tools

READ_TOOLS = {"current_time", "list_calendars", "list_events", "search_events", "get_event", "find_free_slots"}


def tools_by_name(client) -> dict:
    return {t.name: t for t in build_calendar_tools(client)}


def call(tool, **kwargs) -> dict:
    return json.loads(tool.invoke(kwargs))


def test_full_toolset_exposes_reads_and_writes(client):
    assert set(tools_by_name(client)) == READ_TOOLS | set(WRITE_TOOL_NAMES)


def test_every_tool_has_a_description_and_schema(client):
    for tool in build_calendar_tools(client):
        assert tool.description, f"{tool.name} has no description"
        assert tool.args_schema is not None


def test_read_only_client_yields_no_write_tools(fake_service):
    client = GoogleCalendarClient(service=fake_service, settings=CalendarSettings(read_only=True))
    assert set(tools_by_name(client)) == READ_TOOLS


def test_write_tools_cannot_be_forced_onto_a_read_only_client(fake_service):
    client = GoogleCalendarClient(service=fake_service, settings=CalendarSettings(read_only=True))
    with pytest.raises(ValueError):
        build_calendar_tools(client, include_write=True)


def test_current_time_reports_the_configured_zone(client):
    payload = call(tools_by_name(client)["current_time"])
    assert payload["ok"] is True
    assert payload["time_zone"] == "Europe/Rome"
    assert payload["weekday"]


def test_list_events_returns_compact_summaries(client):
    payload = call(tools_by_name(client)["list_events"], time_min="2026-09-17", time_max="2026-09-18")
    assert payload["count"] == 2
    assert payload["events"][0]["id"] == "evt_1"
    assert "attendees" in payload["events"][1]


def test_search_events_echoes_the_query(client):
    payload = call(tools_by_name(client)["search_events"], query="acme")
    assert payload["query"] == "acme"
    assert payload["count"] == 1


def test_get_event_missing_id_returns_a_recoverable_error(client):
    payload = call(tools_by_name(client)["get_event"], event_id="nope")
    assert payload["ok"] is False
    assert payload["error_type"] == "EventNotFoundError"


def test_bad_arguments_return_json_not_an_exception(client):
    payload = call(
        tools_by_name(client)["create_event"], summary="X", start="next tuesday", duration_minutes=30
    )
    assert payload["ok"] is False
    assert payload["error_type"] == "TimeParseError"


def test_create_event_missing_end_and_duration_is_reported(client):
    payload = call(tools_by_name(client)["create_event"], summary="X", start="2026-09-18T10:00")
    assert payload["ok"] is False


def test_create_event_happy_path(client, fake_service):
    payload = call(
        tools_by_name(client)["create_event"],
        summary="Sync",
        start="2026-09-18T10:00",
        duration_minutes=30,
        attendees=["mario@acme.it"],
    )
    assert payload["ok"] is True
    assert payload["created"]["summary"] == "Sync"
    assert fake_service.calls[-1][1]["sendUpdates"] == "none"


def test_create_event_notify_flag_maps_to_send_updates(client, fake_service):
    call(
        tools_by_name(client)["create_event"],
        summary="Sync",
        start="2026-09-18T10:00",
        duration_minutes=30,
        notify_attendees=True,
    )
    assert fake_service.calls[-1][1]["sendUpdates"] == "all"


def test_moving_only_the_start_carries_the_duration(client, fake_service):
    """Standup is 09:00–09:15; moving it to 11:00 must not leave the end at 09:15."""
    payload = call(tools_by_name(client)["update_event"], event_id="evt_1", start="2026-09-17T11:00")
    assert payload["ok"] is True
    body = fake_service.calls[-1][1]["body"]
    assert body["start"]["dateTime"].startswith("2026-09-17T11:00")
    assert body["end"]["dateTime"].startswith("2026-09-17T11:15")
    assert body["start"]["timeZone"] == "Europe/Rome"


def test_relative_update_resolves_from_the_event_not_from_now(client, fake_service):
    call(tools_by_name(client)["update_event"], event_id="evt_1", start="+2h")
    body = fake_service.calls[-1][1]["body"]
    assert body["start"]["dateTime"].startswith("2026-09-17T11:00")


def test_updating_an_all_day_event_keeps_date_blocks(client, fake_service):
    fake_service.stored_events["evt_allday"] = {
        "id": "evt_allday",
        "summary": "Ferie",
        "start": {"date": "2026-09-17"},
        "end": {"date": "2026-09-18"},
    }
    payload = call(tools_by_name(client)["update_event"], event_id="evt_allday", start="2026-09-20")
    assert payload["ok"] is True
    body = fake_service.calls[-1][1]["body"]
    assert body["start"] == {"date": "2026-09-20"}
    assert body["end"] == {"date": "2026-09-21"}


def test_update_rejecting_an_end_before_the_start(client):
    payload = call(
        tools_by_name(client)["update_event"],
        event_id="evt_1",
        start="2026-09-17T11:00",
        end="2026-09-17T10:00",
    )
    assert payload["ok"] is False
    assert payload["error_type"] == "TimeParseError"


def test_update_event_with_no_changes_is_rejected(client):
    payload = call(tools_by_name(client)["update_event"], event_id="evt_1")
    assert payload["ok"] is False
    assert payload["error_type"] == "InvalidArguments"


def test_delete_event_returns_a_receipt(client):
    payload = call(tools_by_name(client)["delete_event"], event_id="evt_1")
    assert payload == {"ok": True, "deleted": True, "event_id": "evt_1", "calendar_id": "primary"}


def test_find_free_slots_reports_durations(client, fake_service):
    fake_service.busy = [{"start": "2026-09-17T09:00:00+02:00", "end": "2026-09-17T12:00:00+02:00"}]
    payload = call(
        tools_by_name(client)["find_free_slots"],
        duration_minutes=60,
        time_min="2026-09-17T00:00",
        time_max="2026-09-18T00:00",
    )
    assert payload["count"] == 1
    assert payload["slots"][0]["duration_minutes"] == 360


def test_find_free_slots_accepts_partial_working_hours_override(client, fake_service):
    fake_service.busy = []
    payload = call(
        tools_by_name(client)["find_free_slots"],
        duration_minutes=60,
        time_min="2026-09-17T00:00",
        time_max="2026-09-18T00:00",
        work_start_hour=14,
    )
    assert payload["slots"][0]["start"].endswith("14:00:00+02:00")


def test_dry_run_is_reported_back_to_the_model(fake_service):
    client = GoogleCalendarClient(service=fake_service, settings=CalendarSettings(dry_run=True))
    payload = call(
        tools_by_name(client)["create_event"],
        summary="Sync",
        start="2026-09-18T10:00",
        duration_minutes=30,
    )
    assert payload["dry_run"] is True


def test_listings_carry_the_untrusted_content_note(client):
    """Event text is attacker-reachable; the model is told so in the payload itself."""
    from deepagents_gcal.tools import UNTRUSTED_NOTE

    for payload in (
        call(tools_by_name(client)["list_events"]),
        call(tools_by_name(client)["search_events"], query="acme"),
        call(tools_by_name(client)["get_event"], event_id="evt_1"),
    ):
        assert payload["content_note"] == UNTRUSTED_NOTE


def test_listings_report_truncation(client):
    payload = call(tools_by_name(client)["list_events"], max_results=1)
    assert payload["count"] == 1
    assert payload["truncated"] is True
    assert call(tools_by_name(client)["list_events"], max_results=10)["truncated"] is False


def test_find_free_slots_echoes_the_filters_it_applied(client, fake_service):
    fake_service.busy = []
    payload = call(
        tools_by_name(client)["find_free_slots"],
        duration_minutes=60,
        time_min="2026-09-19T00:00",
        time_max="2026-09-20T00:00",
    )
    # 19 Sep 2026 is a Saturday: zero slots, and the echo explains why.
    assert payload["count"] == 0
    assert payload["searched"]["weekdays_only"] is True
    assert payload["searched"]["working_hours"] == [9, 18]


def test_tools_refuse_a_calendar_outside_the_allowlist(fake_service):
    client = GoogleCalendarClient(
        service=fake_service,
        settings=CalendarSettings(
            calendar_id="team@studio.it", allowed_calendar_ids=["team@studio.it"]
        ),
    )
    payload = call(tools_by_name(client)["list_events"], calendar_id="primary")
    assert payload["ok"] is False
    assert payload["error_type"] == "CalendarNotAllowedError"


def test_unreadable_calendar_is_an_error_not_an_empty_schedule(client, fake_service):
    fake_service.freebusy_errors = {"typo@acme.it": [{"reason": "notFound"}]}
    payload = call(
        tools_by_name(client)["find_free_slots"],
        duration_minutes=60,
        calendar_ids=["typo@acme.it"],
    )
    assert payload["ok"] is False
    assert "typo@acme.it" in payload["error"]
