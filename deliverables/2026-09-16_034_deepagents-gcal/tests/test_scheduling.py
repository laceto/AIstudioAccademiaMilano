"""Free-slot arithmetic — the part most likely to double-book someone."""

from __future__ import annotations

from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

import pytest

from deepagents_gcal.scheduling import (
    find_free_slots,
    merge_intervals,
    subtract_busy,
    working_windows,
)

TZ = "Europe/Rome"
ZONE = ZoneInfo(TZ)


def dt(day: int, hour: int, minute: int = 0) -> datetime:
    return datetime(2026, 9, day, hour, minute, tzinfo=ZONE)


def test_merge_intervals_coalesces_overlaps_and_touches():
    merged = merge_intervals(
        [(dt(17, 10), dt(17, 11)), (dt(17, 10, 30), dt(17, 12)), (dt(17, 12), dt(17, 13))]
    )
    assert merged == [(dt(17, 10), dt(17, 13))]


def test_merge_intervals_keeps_disjoint_blocks_sorted():
    merged = merge_intervals([(dt(17, 15), dt(17, 16)), (dt(17, 9), dt(17, 10))])
    assert merged == [(dt(17, 9), dt(17, 10)), (dt(17, 15), dt(17, 16))]


def test_working_windows_clip_to_working_hours():
    windows = working_windows(dt(17, 0), dt(18, 0), TZ, (9, 18))
    assert windows == [(dt(17, 9), dt(17, 18))]


def test_working_windows_skip_the_weekend():
    # 19 Sep 2026 is a Saturday; 21 Sep is the following Monday.
    windows = working_windows(dt(18, 0), dt(22, 0), TZ, (9, 18))
    days = {start.day for start, _ in windows}
    assert days == {18, 21}


def test_working_windows_can_include_the_weekend():
    windows = working_windows(dt(18, 0), dt(22, 0), TZ, (9, 18), weekdays_only=False)
    assert {start.day for start, _ in windows} == {18, 19, 20, 21}


def test_working_windows_reject_impossible_hours():
    with pytest.raises(ValueError):
        working_windows(dt(17, 0), dt(18, 0), TZ, (18, 9))


def test_working_windows_start_at_the_request_time_not_the_day_start():
    windows = working_windows(dt(17, 14), dt(17, 23), TZ, (9, 18))
    assert windows == [(dt(17, 14), dt(17, 18))]


def test_subtract_busy_carves_gaps_around_meetings():
    slots = subtract_busy(
        [(dt(17, 9), dt(17, 18))],
        [(dt(17, 10), dt(17, 11)), (dt(17, 14), dt(17, 15))],
        timedelta(minutes=60),
    )
    assert [(s.start, s.end) for s in slots] == [
        (dt(17, 9), dt(17, 10)),
        (dt(17, 11), dt(17, 14)),
        (dt(17, 15), dt(17, 18)),
    ]


def test_subtract_busy_drops_gaps_that_are_too_short():
    slots = subtract_busy(
        [(dt(17, 9), dt(17, 18))],
        [(dt(17, 9, 30), dt(17, 17, 45))],
        timedelta(minutes=60),
    )
    assert slots == []


def test_subtract_busy_handles_a_fully_booked_window():
    assert subtract_busy([(dt(17, 9), dt(17, 18))], [(dt(17, 8), dt(17, 19))], timedelta(minutes=30)) == []


def test_find_free_slots_respects_the_limit():
    slots = find_free_slots([], dt(17, 0), dt(24, 0), 30, TZ, (9, 18), limit=2)
    assert len(slots) == 2


def test_find_free_slots_ignores_busy_blocks_outside_working_hours():
    slots = find_free_slots([(dt(17, 20), dt(17, 22))], dt(17, 0), dt(18, 0), 60, TZ, (9, 18))
    assert [(s.start, s.end) for s in slots] == [(dt(17, 9), dt(17, 18))]


def test_find_free_slots_validates_arguments():
    with pytest.raises(ValueError):
        find_free_slots([], dt(17, 0), dt(18, 0), 0, TZ)
    with pytest.raises(ValueError):
        find_free_slots([], dt(18, 0), dt(17, 0), 30, TZ)
