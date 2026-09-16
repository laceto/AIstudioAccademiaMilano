"""Typed models for calendars, events and free slots.

These are the package's public data contract: the client returns them, the tools
serialise them, and downstream developers can build on them without ever
touching a raw Google API payload.
"""

from __future__ import annotations

from datetime import datetime, timedelta
from datetime import time as time_cls
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from .errors import TimeParseError
from .timeutils import is_date_only, parse_datetime, to_rfc3339

#: Event descriptions can be arbitrarily long; anything past this is noise in a prompt.
MAX_DESCRIPTION_CHARS = 1000


def _clip(value: str | None, limit: int) -> str | None:
    """Truncate untrusted free text, marking that it was cut."""
    if value is None or len(value) <= limit:
        return value
    return value[:limit] + f"… [truncated, {len(value)} chars total]"


class CalendarRef(BaseModel):
    """A calendar the authenticated account can see."""

    model_config = ConfigDict(extra="ignore")

    id: str
    summary: str = ""
    description: str | None = None
    time_zone: str | None = None
    access_role: str | None = None
    primary: bool = False

    @classmethod
    def from_api(cls, payload: dict[str, Any]) -> "CalendarRef":
        return cls(
            id=payload["id"],
            summary=payload.get("summary", ""),
            description=payload.get("description"),
            time_zone=payload.get("timeZone"),
            access_role=payload.get("accessRole"),
            primary=bool(payload.get("primary", False)),
        )


class EventTime(BaseModel):
    """One end of an event — either a timed instant or an all-day date."""

    model_config = ConfigDict(extra="ignore")

    date_time: datetime | None = None
    date: str | None = None
    time_zone: str | None = None

    @model_validator(mode="after")
    def _one_of(self) -> "EventTime":
        if (self.date_time is None) == (self.date is None):
            raise ValueError("EventTime needs exactly one of date_time or date")
        return self

    @property
    def all_day(self) -> bool:
        return self.date is not None

    @classmethod
    def from_api(cls, payload: dict[str, Any]) -> "EventTime":
        raw = payload.get("dateTime")
        if raw:
            declared = payload.get("timeZone")
            try:
                parsed = parse_datetime(raw, declared or "UTC")
            except TimeParseError:
                # A Google dateTime always carries its own offset; the zone name is only
                # a fallback. An unusable one must not take the whole listing down.
                parsed = parse_datetime(raw, "UTC")
            return cls(date_time=parsed, time_zone=declared)
        return cls(date=payload.get("date"), time_zone=payload.get("timeZone"))

    def to_api(self) -> dict[str, Any]:
        if self.date is not None:
            return {"date": self.date}
        body: dict[str, Any] = {"dateTime": to_rfc3339(self.date_time)}  # type: ignore[arg-type]
        if self.time_zone:
            body["timeZone"] = self.time_zone
        return body

    def __str__(self) -> str:
        return self.date if self.date else f"{self.date_time:%Y-%m-%d %H:%M %Z}"


class Event(BaseModel):
    """An existing calendar event, as returned by the API."""

    model_config = ConfigDict(extra="ignore")

    id: str
    calendar_id: str = "primary"
    summary: str = "(no title)"
    description: str | None = None
    location: str | None = None
    start: EventTime
    end: EventTime
    attendees: list[str] = Field(default_factory=list)
    organizer: str | None = None
    status: str | None = None
    html_link: str | None = None
    recurring_event_id: str | None = None

    @classmethod
    def from_api(cls, payload: dict[str, Any], calendar_id: str = "primary") -> "Event":
        return cls(
            id=payload.get("id", ""),
            calendar_id=calendar_id,
            summary=payload.get("summary", "(no title)"),
            description=payload.get("description"),
            location=payload.get("location"),
            start=EventTime.from_api(payload.get("start", {})),
            end=EventTime.from_api(payload.get("end", {})),
            attendees=[a.get("email", "") for a in payload.get("attendees", []) if a.get("email")],
            organizer=(payload.get("organizer") or {}).get("email"),
            status=payload.get("status"),
            html_link=payload.get("htmlLink"),
            recurring_event_id=payload.get("recurringEventId"),
        )

    def to_summary(self) -> dict[str, Any]:
        """Compact dict for LLM consumption — no nulls, no nested noise.

        Event text is written by whoever created the event — including strangers,
        since Google adds emailed invitations to the primary calendar — so free-text
        fields are truncated here before they reach a model context.
        """
        data: dict[str, Any] = {
            "id": self.id,
            "summary": _clip(self.summary, 300),
            "start": str(self.start),
            "end": str(self.end),
        }
        for key, value in (
            ("location", _clip(self.location, 300)),
            ("attendees", self.attendees or None),
            ("description", _clip(self.description, MAX_DESCRIPTION_CHARS)),
            ("status", self.status if self.status not in (None, "confirmed") else None),
            ("link", self.html_link),
        ):
            if value:
                data[key] = value
        return data


class EventDraft(BaseModel):
    """An event to create or patch. Times accept the forgiving formats of `timeutils`."""

    model_config = ConfigDict(extra="forbid")

    summary: str = Field(min_length=1)
    start: str
    end: str | None = None
    duration_minutes: int | None = Field(default=None, gt=0, le=60 * 24 * 7)
    time_zone: str | None = None
    description: str | None = None
    location: str | None = None
    attendees: list[str] = Field(default_factory=list)
    all_day: bool = False
    reminders_minutes: list[int] | None = None
    visibility: Literal["default", "public", "private"] | None = None

    @field_validator("attendees")
    @classmethod
    def _valid_emails(cls, value: list[str]) -> list[str]:
        for email in value:
            if "@" not in email or email.startswith("@") or email.endswith("@"):
                raise ValueError(f"{email!r} is not a valid email address")
        return value

    @model_validator(mode="after")
    def _end_or_duration(self) -> "EventDraft":
        if self.end is None and self.duration_minutes is None:
            raise ValueError("Provide either end or duration_minutes")
        return self

    def resolve(self, default_tz: str, *, reference: datetime | None = None) -> tuple[datetime, datetime, str]:
        """Return `(start, end, timezone)` as aware datetimes, validating the order."""
        tz = self.time_zone or default_tz
        start = parse_datetime(self.start, tz, reference=reference)
        if self.end is not None:
            end = parse_datetime(self.end, tz, reference=start)
        else:
            end = start + timedelta(minutes=self.duration_minutes or 0)
        if end <= start:
            raise TimeParseError(f"Event end ({end.isoformat()}) must be after start ({start.isoformat()})")
        return start, end, tz

    def to_api(self, default_tz: str, *, reference: datetime | None = None) -> dict[str, Any]:
        """Build the Google Calendar `events.insert` body."""
        start, end, tz = self.resolve(default_tz, reference=reference)
        if self.all_day or (is_date_only(self.start) and self.end and is_date_only(self.end)):
            # Google treats an all-day `end.date` as exclusive and rejects a body whose
            # end is not strictly after its start, so a sub-day duration (the natural way
            # to say "block tomorrow") has to round up to the next date boundary.
            end_date = end.date()
            if end.time() != time_cls(0, 0):
                end_date += timedelta(days=1)
            end_date = max(end_date, start.date() + timedelta(days=1))
            start_block: dict[str, Any] = {"date": f"{start:%Y-%m-%d}"}
            end_block: dict[str, Any] = {"date": f"{end_date:%Y-%m-%d}"}
        else:
            start_block = {"dateTime": to_rfc3339(start), "timeZone": tz}
            end_block = {"dateTime": to_rfc3339(end), "timeZone": tz}

        body: dict[str, Any] = {"summary": self.summary, "start": start_block, "end": end_block}
        if self.description:
            body["description"] = self.description
        if self.location:
            body["location"] = self.location
        if self.attendees:
            body["attendees"] = [{"email": email} for email in self.attendees]
        if self.visibility:
            body["visibility"] = self.visibility
        if self.reminders_minutes is not None:
            body["reminders"] = {
                "useDefault": False,
                "overrides": [{"method": "popup", "minutes": m} for m in self.reminders_minutes],
            }
        return body


class FreeSlot(BaseModel):
    """A gap in the schedule long enough for the requested meeting."""

    start: datetime
    end: datetime

    @property
    def duration_minutes(self) -> int:
        return int((self.end - self.start).total_seconds() // 60)

    def to_summary(self) -> dict[str, Any]:
        return {
            "start": to_rfc3339(self.start),
            "end": to_rfc3339(self.end),
            "duration_minutes": self.duration_minutes,
        }
