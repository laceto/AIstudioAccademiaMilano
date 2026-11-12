"""`GoogleCalendarClient` — a small, typed wrapper over Google Calendar API v3.

Design notes for anyone extending this:

* The Google service object is injectable. Pass `service=<fake>` in tests and
  nothing in this module touches the network.
* Writes go through `_guard_write`, which enforces `read_only` and `dry_run`
  before any request is built — the agent can be handed a client it simply
  cannot use to mutate a calendar.
* API failures are translated into `ApiError` / `EventNotFoundError` so callers
  never have to import `googleapiclient` to handle errors.
"""

from __future__ import annotations

import inspect
from datetime import datetime, timedelta
from typing import Any, Literal

from . import scheduling
from .config import CalendarSettings
from .errors import ApiError, CalendarNotAllowedError, EventNotFoundError, ReadOnlyError
from .models import CalendarRef, Event, EventDraft, FreeSlot
from .timeutils import now_in, parse_datetime, to_rfc3339

SendUpdates = Literal["none", "all", "externalOnly"]

#: Google's raw error bodies carry request URIs and response payloads; those end up in a
#: model's context and in logs, so only the head of the message is kept.
MAX_ERROR_CHARS = 300


def _accepts_num_retries(execute: Any) -> bool:
    try:
        parameters = inspect.signature(execute).parameters
    except (TypeError, ValueError):  # pragma: no cover - builtins without signatures
        return False
    return "num_retries" in parameters or any(
        p.kind is inspect.Parameter.VAR_KEYWORD for p in parameters.values()
    )


def _clip_error(exc: Exception) -> str:
    message = " ".join(str(exc).split())
    return message if len(message) <= MAX_ERROR_CHARS else message[:MAX_ERROR_CHARS] + "…"


class GoogleCalendarClient:
    """Typed access to one Google account's calendars."""

    def __init__(
        self,
        service: Any | None = None,
        settings: CalendarSettings | None = None,
    ) -> None:
        self.settings = settings or CalendarSettings()
        self._service = service

    # ── construction ────────────────────────────────────────────────────────

    @classmethod
    def from_env(cls, **overrides: Any) -> "GoogleCalendarClient":
        """Build a client from `GCAL_*` environment variables."""
        return cls(settings=CalendarSettings.from_env(**overrides))

    @property
    def service(self) -> Any:
        """The Google API service, built (and authenticated) on first use."""
        if self._service is None:
            from .auth import build_service

            self._service = build_service(self.settings)
        return self._service

    @property
    def timezone(self) -> str:
        return self.settings.timezone

    # ── guards ──────────────────────────────────────────────────────────────

    def _guard_write(self, operation: str) -> None:
        if self.settings.read_only:
            raise ReadOnlyError(
                f"{operation} refused: this client is read-only. "
                "Rebuild it with read_only=False (and re-authorise with write scopes)."
            )

    def _calendar(self, calendar_id: str | None) -> str:
        """Resolve the target calendar, enforcing the allowlist when one is configured.

        Google has no per-calendar OAuth scope, so without this an agent can name any
        calendar the account can reach — `settings.calendar_id` alone is a default,
        never a boundary.
        """
        resolved = calendar_id or self.settings.calendar_id
        allowed = self.settings.allowed_calendar_ids
        if allowed is not None and resolved not in allowed:
            raise CalendarNotAllowedError(
                f"Calendar {resolved!r} is not in this client's allowed_calendar_ids "
                f"({', '.join(allowed)})."
            )
        return resolved

    def _execute(self, request: Any, *, context: str) -> Any:
        """Run a Google request, retrying transient failures and normalising errors.

        `num_retries` is googleapiclient's own exponential backoff, which covers the
        429 and 5xx responses Calendar hands out routinely.
        """
        execute = request.execute
        # Only pass num_retries to an execute() that accepts it: a caller-supplied service
        # (or a test double) may not, and retrying a failed call blindly could duplicate a
        # write.
        kwargs = {"num_retries": self.settings.max_retries} if _accepts_num_retries(execute) else {}
        try:
            return execute(**kwargs)
        except Exception as exc:  # noqa: BLE001 - normalised below
            status = getattr(getattr(exc, "resp", None), "status", None)
            if status == 404:
                raise EventNotFoundError(f"{context}: not found") from exc
            if status in (401, 403):
                raise ApiError(
                    f"{context}: access denied by Google ({status}). "
                    "Check the granted scopes and calendar sharing settings.",
                    status=status,
                ) from exc
            raise ApiError(f"{context}: {_clip_error(exc)}", status=status) from exc

    # ── reads ───────────────────────────────────────────────────────────────

    def list_calendars(self) -> list[CalendarRef]:
        """Every calendar in the account's calendar list."""
        payload = self._execute(
            self.service.calendarList().list(), context="list_calendars"
        )
        return [CalendarRef.from_api(item) for item in payload.get("items", [])]

    def list_events(
        self,
        *,
        calendar_id: str | None = None,
        time_min: str | datetime | None = None,
        time_max: str | datetime | None = None,
        query: str | None = None,
        max_results: int | None = None,
    ) -> list[Event]:
        """Events in a window, single-expanded and ordered by start time."""
        tz = self.timezone
        reference = now_in(tz)
        start = parse_datetime(time_min, tz, reference=reference) if time_min else reference
        end = (
            parse_datetime(time_max, tz, reference=start)
            if time_max
            else start + timedelta(days=7)
        )
        calendar_id = self._calendar(calendar_id)
        limit = max_results or self.settings.max_results
        params: dict[str, Any] = {
            "calendarId": calendar_id,
            "timeMin": to_rfc3339(start),
            "timeMax": to_rfc3339(end),
            "singleEvents": True,
            "orderBy": "startTime",
            "maxResults": limit,
        }
        if query:
            params["q"] = query

        events: list[Event] = []
        page_token: str | None = None
        while True:
            if page_token:
                params["pageToken"] = page_token
            payload = self._execute(
                self.service.events().list(**params), context=f"list_events({calendar_id})"
            )
            for item in payload.get("items", []):
                # Cancelled instances of a recurring series arrive as id+status only, with
                # no start/end. They are not events the caller can act on — drop them
                # rather than fail the whole listing.
                if item.get("start") and item.get("end"):
                    events.append(Event.from_api(item, calendar_id))
            page_token = payload.get("nextPageToken")
            # Keep following pages only while the caller's cap leaves room: a page can come
            # back short of `limit` purely because cancelled instances were filtered out.
            if not page_token or len(events) >= limit:
                break
        return events[:limit]

    def search_events(
        self,
        query: str,
        *,
        calendar_id: str | None = None,
        days_ahead: int = 30,
        days_back: int = 7,
        max_results: int | None = None,
    ) -> list[Event]:
        """Full-text search across a window centred on today."""
        reference = now_in(self.timezone)
        return self.list_events(
            calendar_id=calendar_id,
            time_min=reference - timedelta(days=days_back),
            time_max=reference + timedelta(days=days_ahead),
            query=query,
            max_results=max_results,
        )

    def get_event(self, event_id: str, *, calendar_id: str | None = None) -> Event:
        calendar_id = self._calendar(calendar_id)
        payload = self._execute(
            self.service.events().get(calendarId=calendar_id, eventId=event_id),
            context=f"get_event({event_id})",
        )
        if not (payload.get("start") and payload.get("end")):
            # A cancelled instance still resolves by id, but carries no times.
            raise EventNotFoundError(
                f"get_event({event_id}): event is cancelled or has no start/end"
            )
        return Event.from_api(payload, calendar_id)

    def busy_intervals(
        self,
        time_min: datetime,
        time_max: datetime,
        *,
        calendar_ids: list[str] | None = None,
    ) -> list[tuple[datetime, datetime]]:
        """Busy blocks from the freebusy endpoint, across one or more calendars."""
        ids = [self._calendar(cid) for cid in (calendar_ids or [self.settings.calendar_id])]
        body = {
            "timeMin": to_rfc3339(time_min),
            "timeMax": to_rfc3339(time_max),
            "timeZone": self.timezone,
            "items": [{"id": cid} for cid in ids],
        }
        payload = self._execute(
            self.service.freebusy().query(body=body), context="freebusy"
        )
        calendars = payload.get("calendars") or {}
        unreadable = {
            cid: [e.get("reason", "unknown") for e in data.get("errors", [])]
            for cid, data in calendars.items()
            if data.get("errors")
        }
        if unreadable:
            # Without this the endpoint reports an unreadable calendar as simply free,
            # and a mistyped colleague address turns into a confident double-booking.
            detail = "; ".join(f"{cid}: {', '.join(reasons)}" for cid, reasons in unreadable.items())
            raise ApiError(f"freebusy: could not read {detail}")

        intervals: list[tuple[datetime, datetime]] = []
        for calendar in calendars.values():
            for block in calendar.get("busy", []):
                intervals.append(
                    (
                        parse_datetime(block["start"], self.timezone),
                        parse_datetime(block["end"], self.timezone),
                    )
                )
        return intervals

    def find_free_slots(
        self,
        duration_minutes: int,
        *,
        time_min: str | datetime | None = None,
        time_max: str | datetime | None = None,
        calendar_ids: list[str] | None = None,
        working_hours: tuple[int, int] | None = None,
        weekdays_only: bool = True,
        limit: int = 10,
    ) -> list[FreeSlot]:
        """Gaps long enough for a meeting, inside working hours."""
        tz = self.timezone
        reference = now_in(tz)
        start = parse_datetime(time_min, tz, reference=reference) if time_min else reference
        end = (
            parse_datetime(time_max, tz, reference=start)
            if time_max
            else start + timedelta(days=7)
        )
        busy = self.busy_intervals(start, end, calendar_ids=calendar_ids)
        return scheduling.find_free_slots(
            busy,
            start,
            end,
            duration_minutes,
            tz,
            working_hours or self.settings.working_hours,
            weekdays_only=weekdays_only,
            limit=limit,
        )

    # ── writes ──────────────────────────────────────────────────────────────

    def create_event(
        self,
        draft: EventDraft,
        *,
        calendar_id: str | None = None,
        send_updates: SendUpdates = "none",
    ) -> Event:
        """Create an event. Honours `read_only` and `dry_run`."""
        self._guard_write("create_event")
        calendar_id = self._calendar(calendar_id)
        body = draft.to_api(self.timezone)
        if self.settings.dry_run:
            return Event.from_api({**body, "id": "dry-run", "status": "dry_run"}, calendar_id)
        payload = self._execute(
            self.service.events().insert(
                calendarId=calendar_id, body=body, sendUpdates=send_updates
            ),
            context=f"create_event({draft.summary!r})",
        )
        return Event.from_api(payload, calendar_id)

    def update_event(
        self,
        event_id: str,
        changes: dict[str, Any],
        *,
        calendar_id: str | None = None,
        send_updates: SendUpdates = "none",
    ) -> Event:
        """Patch an existing event with a partial Google-shaped body."""
        self._guard_write("update_event")
        if not changes:
            raise ValueError("update_event needs at least one field to change")
        calendar_id = self._calendar(calendar_id)
        if self.settings.dry_run:
            current = self.get_event(event_id, calendar_id=calendar_id)
            preview = {
                "id": event_id,
                "summary": current.summary,
                "location": current.location,
                "description": current.description,
                "start": current.start.to_api(),
                "end": current.end.to_api(),
                **changes,
                "status": "dry_run",
            }
            return Event.from_api(preview, calendar_id)
        payload = self._execute(
            self.service.events().patch(
                calendarId=calendar_id, eventId=event_id, body=changes, sendUpdates=send_updates
            ),
            context=f"update_event({event_id})",
        )
        return Event.from_api(payload, calendar_id)

    def delete_event(
        self,
        event_id: str,
        *,
        calendar_id: str | None = None,
        send_updates: SendUpdates = "none",
    ) -> dict[str, Any]:
        """Delete an event. Returns a small receipt rather than raising on success."""
        self._guard_write("delete_event")
        calendar_id = self._calendar(calendar_id)
        if self.settings.dry_run:
            return {"deleted": False, "dry_run": True, "event_id": event_id, "calendar_id": calendar_id}
        self._execute(
            self.service.events().delete(
                calendarId=calendar_id, eventId=event_id, sendUpdates=send_updates
            ),
            context=f"delete_event({event_id})",
        )
        return {"deleted": True, "event_id": event_id, "calendar_id": calendar_id}
