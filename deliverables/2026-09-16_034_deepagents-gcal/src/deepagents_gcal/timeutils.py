"""Datetime parsing and formatting helpers.

LLMs are unreliable at date arithmetic, so the tool layer accepts a small set of
forgiving formats and normalises everything to timezone-aware ISO 8601 before it
reaches the Google Calendar API:

* ISO 8601, with or without an offset (``2026-09-17T10:00``)
* date only (``2026-09-17``) — used for all-day events
* the keywords ``now``, ``today``, ``tomorrow``, ``yesterday``
* relative offsets (``+2h``, ``-30m``, ``+3d``, ``+1w``)

Everything here is pure: no network, no Google client libraries.
"""

from __future__ import annotations

import re
from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from .errors import TimeParseError

_RELATIVE_RE = re.compile(r"^([+-])(\d+)\s*([mhdw])$", re.IGNORECASE)
_UNIT_TO_KWARG = {"m": "minutes", "h": "hours", "d": "days", "w": "weeks"}

DATE_ONLY_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")


def get_timezone(name: str) -> ZoneInfo:
    """Return a `ZoneInfo`, raising `TimeParseError` for unknown zone names."""
    try:
        return ZoneInfo(name)
    except (ZoneInfoNotFoundError, ValueError) as exc:  # pragma: no cover - platform dependent
        raise TimeParseError(f"Unknown timezone {name!r}") from exc


def now_in(tz: str) -> datetime:
    """Current time in the given IANA timezone."""
    return datetime.now(tz=get_timezone(tz))


def is_date_only(value: str) -> bool:
    """True when the string is a bare calendar date (all-day event notation)."""
    return bool(DATE_ONLY_RE.match(value.strip()))


def parse_datetime(value: str | datetime | date, tz: str, *, reference: datetime | None = None) -> datetime:
    """Parse `value` into a timezone-aware datetime in `tz`.

    `reference` fixes "now" for relative expressions — it exists so tests can be
    deterministic; production callers leave it as `None`.
    """
    zone = get_timezone(tz)
    ref = reference or datetime.now(tz=zone)
    if ref.tzinfo is None:
        ref = ref.replace(tzinfo=zone)

    if isinstance(value, datetime):
        return value if value.tzinfo else value.replace(tzinfo=zone)
    if isinstance(value, date):
        return datetime(value.year, value.month, value.day, tzinfo=zone)

    raw = str(value).strip()
    if not raw:
        raise TimeParseError("Empty datetime string")

    lowered = raw.lower()
    if lowered == "now":
        return ref
    if lowered == "today":
        return ref.replace(hour=0, minute=0, second=0, microsecond=0)
    if lowered == "tomorrow":
        return (ref + timedelta(days=1)).replace(hour=0, minute=0, second=0, microsecond=0)
    if lowered == "yesterday":
        return (ref - timedelta(days=1)).replace(hour=0, minute=0, second=0, microsecond=0)

    relative = _RELATIVE_RE.match(lowered)
    if relative:
        sign, amount, unit = relative.groups()
        delta = timedelta(**{_UNIT_TO_KWARG[unit.lower()]: int(amount)})
        return ref + delta if sign == "+" else ref - delta

    candidate = raw.replace("Z", "+00:00") if raw.endswith("Z") else raw
    try:
        parsed = datetime.fromisoformat(candidate)
    except ValueError as exc:
        raise TimeParseError(
            f"Cannot parse {raw!r}. Use ISO 8601 (2026-09-17T10:00), a date "
            "(2026-09-17), 'now'/'today'/'tomorrow', or an offset such as '+2h'."
        ) from exc
    return parsed if parsed.tzinfo else parsed.replace(tzinfo=zone)


def to_rfc3339(value: datetime) -> str:
    """Format an aware datetime the way the Google Calendar API expects it."""
    if value.tzinfo is None:
        raise TimeParseError("Refusing to serialise a naive datetime; attach a timezone first")
    return value.isoformat()


def day_bounds(day: datetime, tz: str) -> tuple[datetime, datetime]:
    """Midnight-to-midnight bounds of `day`, in `tz`."""
    zone = get_timezone(tz)
    local = day.astimezone(zone)
    start = local.replace(hour=0, minute=0, second=0, microsecond=0)
    return start, start + timedelta(days=1)


def humanize_range(start: datetime, end: datetime) -> str:
    """Compact human label for a time range, e.g. `2026-09-17 10:00–11:30`."""
    if start.date() == end.date():
        return f"{start:%Y-%m-%d %H:%M}–{end:%H:%M}"
    return f"{start:%Y-%m-%d %H:%M} → {end:%Y-%m-%d %H:%M}"
