"""Datetime parsing — the layer that absorbs sloppy LLM date arguments."""

from __future__ import annotations

from datetime import datetime, timezone
from zoneinfo import ZoneInfo

import pytest

from deepagents_gcal.errors import TimeParseError
from deepagents_gcal.timeutils import (
    day_bounds,
    get_timezone,
    humanize_range,
    is_date_only,
    now_in,
    parse_datetime,
    to_rfc3339,
)

TZ = "Europe/Rome"
REF = datetime(2026, 9, 16, 15, 30, tzinfo=ZoneInfo(TZ))


def test_parses_iso_with_offset():
    parsed = parse_datetime("2026-09-17T10:00:00+02:00", TZ)
    assert parsed == datetime(2026, 9, 17, 10, 0, tzinfo=ZoneInfo(TZ))


def test_naive_iso_gets_the_configured_timezone():
    parsed = parse_datetime("2026-09-17T10:00", TZ)
    assert parsed.tzinfo is not None
    assert parsed.utcoffset() == ZoneInfo(TZ).utcoffset(parsed)


def test_zulu_suffix_is_understood():
    assert parse_datetime("2026-09-17T08:00:00Z", TZ).hour == 8
    assert parse_datetime("2026-09-17T08:00:00Z", TZ).utcoffset().total_seconds() == 0


def test_date_only_becomes_midnight():
    assert parse_datetime("2026-09-17", TZ) == datetime(2026, 9, 17, tzinfo=ZoneInfo(TZ))


@pytest.mark.parametrize(
    ("keyword", "expected_day"),
    [("today", 16), ("tomorrow", 17), ("yesterday", 15)],
)
def test_keywords_resolve_against_the_reference(keyword, expected_day):
    parsed = parse_datetime(keyword, TZ, reference=REF)
    assert (parsed.day, parsed.hour) == (expected_day, 0)


def test_now_returns_the_reference_instant():
    assert parse_datetime("now", TZ, reference=REF) == REF


@pytest.mark.parametrize(
    ("offset", "expected"),
    [
        ("+2h", datetime(2026, 9, 16, 17, 30, tzinfo=ZoneInfo(TZ))),
        ("-30m", datetime(2026, 9, 16, 15, 0, tzinfo=ZoneInfo(TZ))),
        ("+3d", datetime(2026, 9, 19, 15, 30, tzinfo=ZoneInfo(TZ))),
        ("+1w", datetime(2026, 9, 23, 15, 30, tzinfo=ZoneInfo(TZ))),
    ],
)
def test_relative_offsets(offset, expected):
    assert parse_datetime(offset, TZ, reference=REF) == expected


@pytest.mark.parametrize("bad", ["", "next tuesday", "17/09/2026", "soon"])
def test_unparseable_input_raises(bad):
    with pytest.raises(TimeParseError):
        parse_datetime(bad, TZ)


def test_unknown_timezone_raises():
    with pytest.raises(TimeParseError):
        parse_datetime("2026-09-17", "Mars/Olympus")


def test_datetime_passthrough_keeps_awareness():
    aware = datetime(2026, 9, 17, 10, tzinfo=ZoneInfo("UTC"))
    assert parse_datetime(aware, TZ) is aware


def test_to_rfc3339_rejects_naive_datetimes():
    with pytest.raises(TimeParseError):
        to_rfc3339(datetime(2026, 9, 17, 10, 0))


def test_is_date_only():
    assert is_date_only("2026-09-17")
    assert not is_date_only("2026-09-17T10:00")


def test_day_bounds_span_exactly_one_day():
    start, end = day_bounds(REF, TZ)
    assert start.hour == 0 and (end - start).days == 1


def test_now_in_is_timezone_aware():
    assert now_in(TZ).tzinfo is not None


def test_humanize_range_collapses_same_day():
    start = datetime(2026, 9, 17, 10, 0, tzinfo=ZoneInfo(TZ))
    end = datetime(2026, 9, 17, 11, 30, tzinfo=ZoneInfo(TZ))
    assert humanize_range(start, end) == "2026-09-17 10:00–11:30"
    assert "→" in humanize_range(start, end.replace(day=18))


def test_hour_offsets_are_elapsed_time_across_a_dst_boundary():
    """25 Oct 2026 02:00 CEST falls back to 01:00 CET; +2h must still be two real hours."""
    before_fallback = datetime(2026, 10, 25, 1, 30, tzinfo=ZoneInfo(TZ))
    moved = parse_datetime("+2h", TZ, reference=before_fallback)
    # Same-zone subtraction in Python is wall-clock, so elapsed time is measured in UTC.
    elapsed = moved.astimezone(timezone.utc) - before_fallback.astimezone(timezone.utc)
    assert elapsed.total_seconds() == 2 * 3600
    # Wall clock advances by one hour only, because 02:00 CEST falls back to 01:00 CET.
    assert moved.hour == 2 and moved.utcoffset().total_seconds() == 3600


def test_day_offsets_stay_wall_clock_across_a_dst_boundary():
    before_fallback = datetime(2026, 10, 25, 1, 30, tzinfo=ZoneInfo(TZ))
    moved = parse_datetime("+1d", TZ, reference=before_fallback)
    assert (moved.hour, moved.minute) == (1, 30)


@pytest.mark.parametrize(
    ("name", "offset_hours"),
    [("GMT+02:00", 2), ("GMT-05:00", -5), ("UTC+1", 1), ("GMT+0530", 5.5)],
)
def test_google_fixed_offset_zones_are_accepted(name, offset_hours):
    zone = get_timezone(name)
    assert zone.utcoffset(datetime(2026, 9, 17)).total_seconds() == offset_hours * 3600
