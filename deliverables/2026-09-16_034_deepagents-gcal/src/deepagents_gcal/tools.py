"""LangChain tools that expose a `GoogleCalendarClient` to an agent.

`build_calendar_tools(client)` returns plain `StructuredTool`s, so they work with
deepagents, `create_agent`, a bare LangGraph node, or any other LangChain-compatible
runtime — this package is not the only way to consume them.

Two conventions the agent relies on:

* Every tool returns a JSON string. Success and failure share the shape
  `{"ok": bool, ...}`, so the model can recover from an error instead of stalling.
* Write tools are named in `WRITE_TOOL_NAMES`; `agent.py` wires exactly those into
  the human-approval interrupt.
"""

from __future__ import annotations

import json
from typing import Any, Callable

from langchain_core.tools import BaseTool, StructuredTool
from pydantic import BaseModel, Field

from .client import GoogleCalendarClient
from .errors import CalendarError
from .models import EventDraft
from .timeutils import now_in

#: Tools that mutate a calendar — the set guarded by human-in-the-loop approval.
WRITE_TOOL_NAMES: tuple[str, ...] = ("create_event", "update_event", "delete_event")

_TIME_HELP = (
    "ISO 8601 (2026-09-17T10:00), a date (2026-09-17), 'now'/'today'/'tomorrow', "
    "or an offset such as '+2h'"
)


def _dump(payload: Any) -> str:
    return json.dumps(payload, ensure_ascii=False, default=str)


def _ok(**payload: Any) -> str:
    return _dump({"ok": True, **payload})


def _safe(fn: Callable[..., str]) -> Callable[..., str]:
    """Turn expected calendar failures into a JSON error the model can act on."""

    def wrapper(*args: Any, **kwargs: Any) -> str:
        try:
            return fn(*args, **kwargs)
        except CalendarError as exc:
            return _dump({"ok": False, "error": str(exc), "error_type": type(exc).__name__})
        except (ValueError, TypeError) as exc:
            return _dump({"ok": False, "error": str(exc), "error_type": "InvalidArguments"})

    wrapper.__name__ = fn.__name__
    wrapper.__doc__ = fn.__doc__
    return wrapper


# ── argument schemas ────────────────────────────────────────────────────────


class NoArgs(BaseModel):
    pass


class CurrentTimeArgs(BaseModel):
    time_zone: str | None = Field(default=None, description="IANA timezone; defaults to the agent's configured zone")


class ListEventsArgs(BaseModel):
    time_min: str | None = Field(default=None, description=f"Window start — {_TIME_HELP}. Defaults to now.")
    time_max: str | None = Field(default=None, description=f"Window end — {_TIME_HELP}. Defaults to 7 days out.")
    calendar_id: str | None = Field(default=None, description="Calendar id; defaults to the primary calendar")
    query: str | None = Field(default=None, description="Optional free-text filter")
    max_results: int | None = Field(default=None, ge=1, le=250)


class SearchEventsArgs(BaseModel):
    query: str = Field(description="Free-text search, matched against title, description, attendees")
    days_back: int = Field(default=7, ge=0, le=365)
    days_ahead: int = Field(default=30, ge=0, le=365)
    calendar_id: str | None = None
    max_results: int | None = Field(default=None, ge=1, le=250)


class GetEventArgs(BaseModel):
    event_id: str = Field(description="Event id, as returned by list_events or search_events")
    calendar_id: str | None = None


class CreateEventArgs(BaseModel):
    summary: str = Field(description="Event title")
    start: str = Field(description=f"Start — {_TIME_HELP}")
    end: str | None = Field(default=None, description=f"End — {_TIME_HELP}. Omit when using duration_minutes.")
    duration_minutes: int | None = Field(default=None, gt=0, description="Used when end is omitted")
    time_zone: str | None = None
    description: str | None = None
    location: str | None = None
    attendees: list[str] = Field(default_factory=list, description="Attendee email addresses")
    all_day: bool = False
    reminders_minutes: list[int] | None = Field(default=None, description="Popup reminders, minutes before start")
    calendar_id: str | None = None
    notify_attendees: bool = Field(default=False, description="Send Google invitation emails to attendees")


class UpdateEventArgs(BaseModel):
    event_id: str
    summary: str | None = None
    start: str | None = Field(default=None, description=f"New start — {_TIME_HELP}")
    end: str | None = Field(default=None, description=f"New end — {_TIME_HELP}")
    description: str | None = None
    location: str | None = None
    calendar_id: str | None = None
    notify_attendees: bool = False


class DeleteEventArgs(BaseModel):
    event_id: str
    calendar_id: str | None = None
    notify_attendees: bool = False


class FindFreeSlotsArgs(BaseModel):
    duration_minutes: int = Field(gt=0, description="Length of the meeting to fit")
    time_min: str | None = Field(default=None, description=f"Search from — {_TIME_HELP}")
    time_max: str | None = Field(default=None, description=f"Search until — {_TIME_HELP}")
    calendar_ids: list[str] | None = Field(default=None, description="Check several calendars at once")
    work_start_hour: int | None = Field(default=None, ge=0, le=23)
    work_end_hour: int | None = Field(default=None, ge=1, le=24)
    weekdays_only: bool = True
    limit: int = Field(default=10, ge=1, le=50)


# ── tool factory ────────────────────────────────────────────────────────────


def build_calendar_tools(
    client: GoogleCalendarClient,
    *,
    include_write: bool | None = None,
    include_time: bool = True,
) -> list[BaseTool]:
    """Build the calendar toolset bound to `client`.

    `include_write` defaults to the client's own capability: a read-only client
    never gets write tools, so the model is not tempted to call something that
    can only fail.
    """
    if include_write is None:
        include_write = not client.settings.read_only
    if include_write and client.settings.read_only:
        raise ValueError("Cannot expose write tools on a read-only client")

    default_tz = client.timezone

    @_safe
    def current_time(time_zone: str | None = None) -> str:
        """Current date, time and timezone. Call this before resolving any relative date."""
        tz = time_zone or default_tz
        now = now_in(tz)
        return _ok(
            iso=now.isoformat(),
            date=f"{now:%Y-%m-%d}",
            time=f"{now:%H:%M}",
            weekday=f"{now:%A}",
            time_zone=tz,
        )

    @_safe
    def list_calendars() -> str:
        """List every calendar this account can access, with its id and access role."""
        calendars = client.list_calendars()
        return _ok(
            count=len(calendars),
            calendars=[c.model_dump(exclude_none=True) for c in calendars],
        )

    @_safe
    def list_events(
        time_min: str | None = None,
        time_max: str | None = None,
        calendar_id: str | None = None,
        query: str | None = None,
        max_results: int | None = None,
    ) -> str:
        """List events in a time window, earliest first. Recurring events are expanded."""
        events = client.list_events(
            calendar_id=calendar_id,
            time_min=time_min,
            time_max=time_max,
            query=query,
            max_results=max_results,
        )
        return _ok(count=len(events), events=[e.to_summary() for e in events])

    @_safe
    def search_events(
        query: str,
        days_back: int = 7,
        days_ahead: int = 30,
        calendar_id: str | None = None,
        max_results: int | None = None,
    ) -> str:
        """Find events by keyword across a window around today."""
        events = client.search_events(
            query,
            calendar_id=calendar_id,
            days_back=days_back,
            days_ahead=days_ahead,
            max_results=max_results,
        )
        return _ok(count=len(events), query=query, events=[e.to_summary() for e in events])

    @_safe
    def get_event(event_id: str, calendar_id: str | None = None) -> str:
        """Fetch the full detail of one event by id."""
        event = client.get_event(event_id, calendar_id=calendar_id)
        return _ok(event=event.to_summary())

    @_safe
    def find_free_slots(
        duration_minutes: int,
        time_min: str | None = None,
        time_max: str | None = None,
        calendar_ids: list[str] | None = None,
        work_start_hour: int | None = None,
        work_end_hour: int | None = None,
        weekdays_only: bool = True,
        limit: int = 10,
    ) -> str:
        """Find open slots long enough for a meeting, inside working hours."""
        working_hours = None
        if work_start_hour is not None or work_end_hour is not None:
            start_hour, end_hour = client.settings.working_hours
            working_hours = (
                work_start_hour if work_start_hour is not None else start_hour,
                work_end_hour if work_end_hour is not None else end_hour,
            )
        slots = client.find_free_slots(
            duration_minutes,
            time_min=time_min,
            time_max=time_max,
            calendar_ids=calendar_ids,
            working_hours=working_hours,
            weekdays_only=weekdays_only,
            limit=limit,
        )
        return _ok(count=len(slots), slots=[s.to_summary() for s in slots])

    @_safe
    def create_event(
        summary: str,
        start: str,
        end: str | None = None,
        duration_minutes: int | None = None,
        time_zone: str | None = None,
        description: str | None = None,
        location: str | None = None,
        attendees: list[str] | None = None,
        all_day: bool = False,
        reminders_minutes: list[int] | None = None,
        calendar_id: str | None = None,
        notify_attendees: bool = False,
    ) -> str:
        """Create a calendar event. Confirm the details with the user before calling this."""
        draft = EventDraft(
            summary=summary,
            start=start,
            end=end,
            duration_minutes=duration_minutes,
            time_zone=time_zone,
            description=description,
            location=location,
            attendees=attendees or [],
            all_day=all_day,
            reminders_minutes=reminders_minutes,
        )
        event = client.create_event(
            draft,
            calendar_id=calendar_id,
            send_updates="all" if notify_attendees else "none",
        )
        return _ok(created=event.to_summary(), dry_run=client.settings.dry_run)

    @_safe
    def update_event(
        event_id: str,
        summary: str | None = None,
        start: str | None = None,
        end: str | None = None,
        description: str | None = None,
        location: str | None = None,
        calendar_id: str | None = None,
        notify_attendees: bool = False,
    ) -> str:
        """Change fields of an existing event. Only the fields you pass are touched."""
        from .timeutils import parse_datetime, to_rfc3339

        tz = client.timezone
        changes: dict[str, Any] = {}
        if summary is not None:
            changes["summary"] = summary
        if description is not None:
            changes["description"] = description
        if location is not None:
            changes["location"] = location
        if start is not None:
            changes["start"] = {"dateTime": to_rfc3339(parse_datetime(start, tz)), "timeZone": tz}
        if end is not None:
            changes["end"] = {"dateTime": to_rfc3339(parse_datetime(end, tz)), "timeZone": tz}
        if not changes:
            return _dump({"ok": False, "error": "Nothing to update", "error_type": "InvalidArguments"})
        event = client.update_event(
            event_id,
            changes,
            calendar_id=calendar_id,
            send_updates="all" if notify_attendees else "none",
        )
        return _ok(updated=event.to_summary(), dry_run=client.settings.dry_run)

    @_safe
    def delete_event(
        event_id: str, calendar_id: str | None = None, notify_attendees: bool = False
    ) -> str:
        """Delete an event. Irreversible — always ask the user first."""
        receipt = client.delete_event(
            event_id,
            calendar_id=calendar_id,
            send_updates="all" if notify_attendees else "none",
        )
        return _ok(**receipt)

    specs: list[tuple[Callable[..., str], type[BaseModel]]] = []
    if include_time:
        specs.append((current_time, CurrentTimeArgs))
    specs += [
        (list_calendars, NoArgs),
        (list_events, ListEventsArgs),
        (search_events, SearchEventsArgs),
        (get_event, GetEventArgs),
        (find_free_slots, FindFreeSlotsArgs),
    ]
    if include_write:
        specs += [
            (create_event, CreateEventArgs),
            (update_event, UpdateEventArgs),
            (delete_event, DeleteEventArgs),
        ]

    return [
        StructuredTool.from_function(
            func=fn,
            name=fn.__name__,
            description=(fn.__doc__ or "").strip(),
            args_schema=schema,
        )
        for fn, schema in specs
    ]
