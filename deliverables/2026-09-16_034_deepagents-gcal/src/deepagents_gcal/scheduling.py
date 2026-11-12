"""Pure scheduling arithmetic: merging busy blocks and carving out free slots.

Kept free of both Google and LangChain imports so the trickiest logic in the
package can be unit-tested directly.
"""

from __future__ import annotations

from datetime import datetime, time, timedelta

from .models import FreeSlot
from .timeutils import get_timezone


def merge_intervals(intervals: list[tuple[datetime, datetime]]) -> list[tuple[datetime, datetime]]:
    """Sort and coalesce overlapping or touching intervals."""
    if not intervals:
        return []
    ordered = sorted(intervals, key=lambda pair: pair[0])
    merged = [ordered[0]]
    for start, end in ordered[1:]:
        last_start, last_end = merged[-1]
        if start <= last_end:
            merged[-1] = (last_start, max(last_end, end))
        else:
            merged.append((start, end))
    return merged


def working_windows(
    time_min: datetime,
    time_max: datetime,
    tz: str,
    working_hours: tuple[int, int],
    *,
    weekdays_only: bool = True,
) -> list[tuple[datetime, datetime]]:
    """Split a range into one bookable window per day, clipped to working hours."""
    start_hour, end_hour = working_hours
    if not 0 <= start_hour < end_hour <= 24:
        raise ValueError(f"Invalid working hours {working_hours!r}; need 0 <= start < end <= 24")

    zone = get_timezone(tz)
    cursor = time_min.astimezone(zone)
    limit = time_max.astimezone(zone)
    windows: list[tuple[datetime, datetime]] = []

    day = cursor.replace(hour=0, minute=0, second=0, microsecond=0)
    while day < limit:
        if not (weekdays_only and day.weekday() >= 5):
            window_start = datetime.combine(day.date(), time(hour=start_hour), tzinfo=zone)
            window_end = (
                day + timedelta(days=1)
                if end_hour == 24
                else datetime.combine(day.date(), time(hour=end_hour), tzinfo=zone)
            )
            window_start = max(window_start, cursor)
            window_end = min(window_end, limit)
            if window_start < window_end:
                windows.append((window_start, window_end))
        day += timedelta(days=1)
    return windows


def subtract_busy(
    windows: list[tuple[datetime, datetime]],
    busy: list[tuple[datetime, datetime]],
    duration: timedelta,
) -> list[FreeSlot]:
    """Remove busy blocks from bookable windows, keeping gaps of at least `duration`."""
    merged = merge_intervals(busy)
    slots: list[FreeSlot] = []
    for window_start, window_end in windows:
        cursor = window_start
        for busy_start, busy_end in merged:
            if busy_end <= cursor or busy_start >= window_end:
                continue
            if busy_start - cursor >= duration:
                slots.append(FreeSlot(start=cursor, end=busy_start))
            cursor = max(cursor, busy_end)
            if cursor >= window_end:
                break
        if window_end - cursor >= duration:
            slots.append(FreeSlot(start=cursor, end=window_end))
    return slots


def find_free_slots(
    busy: list[tuple[datetime, datetime]],
    time_min: datetime,
    time_max: datetime,
    duration_minutes: int,
    tz: str,
    working_hours: tuple[int, int] = (9, 18),
    *,
    weekdays_only: bool = True,
    limit: int = 10,
) -> list[FreeSlot]:
    """Free slots of at least `duration_minutes`, within working hours."""
    if duration_minutes <= 0:
        raise ValueError("duration_minutes must be positive")
    if time_max <= time_min:
        raise ValueError("time_max must be after time_min")
    windows = working_windows(time_min, time_max, tz, working_hours, weekdays_only=weekdays_only)
    slots = subtract_busy(windows, busy, timedelta(minutes=duration_minutes))
    return slots[:limit]
