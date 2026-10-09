"""gateway/retention.py — how long a job (which holds what the customer typed) is kept.

One number, used by the Firestore TTL (when a job document is deleted) and by the privacy notice
(what the customer is told). If those two ever disagree, the notice is wrong.
"""

from datetime import datetime, timedelta, timezone

import pytest

from gateway import retention


@pytest.fixture(autouse=True)
def _clean(monkeypatch):
    monkeypatch.delenv("JOB_RETENTION_DAYS", raising=False)


def test_the_default_is_ninety_days():
    assert retention.DEFAULT_RETENTION_DAYS == 90
    assert retention.retention_days() == 90


@pytest.mark.parametrize("value,expected", [("30", 30), (" 365 ", 365), ("1", 1)])
def test_the_environment_can_change_it(monkeypatch, value, expected):
    monkeypatch.setenv("JOB_RETENTION_DAYS", value)
    assert retention.retention_days() == expected


@pytest.mark.parametrize("junk", ["", "abc", "0", "-5", "1.5", "99999"])
def test_nonsense_falls_back_to_the_default(monkeypatch, junk):
    monkeypatch.setenv("JOB_RETENTION_DAYS", junk)
    assert retention.retention_days() == 90


def test_expiry_is_creation_plus_the_retention():
    created = "2026-10-09T10:00:00+00:00"
    assert retention.expiry_for(created) == "2027-01-07T10:00:00+00:00"


def test_expiry_follows_the_configured_days(monkeypatch):
    monkeypatch.setenv("JOB_RETENTION_DAYS", "30")
    assert retention.expiry_for("2026-10-09T10:00:00+00:00") == "2026-11-08T10:00:00+00:00"


def test_expiry_defaults_to_now_plus_the_retention_when_creation_is_unknown():
    before = datetime.now(timezone.utc)
    got = datetime.fromisoformat(retention.expiry_for(None))
    assert before + timedelta(days=89) < got < before + timedelta(days=91)


def test_expiry_accepts_a_naive_timestamp_as_utc():
    assert retention.expiry_for("2026-10-09T10:00:00") == "2027-01-07T10:00:00+00:00"


def test_expiry_survives_a_malformed_timestamp():
    got = datetime.fromisoformat(retention.expiry_for("not a date"))
    assert got > datetime.now(timezone.utc)
