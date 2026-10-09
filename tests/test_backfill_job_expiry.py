"""Tests for scripts/backfill_job_expiry.py — give jobs created before the TTL existed an expire_at.

Dry run by default: it must never write unless --apply is given.
"""

import json

from gateway.jobstore import FileJobStore
from gateway.retention import expiry_for
from scripts import backfill_job_expiry as bf

import pytest

CREATED = "2026-07-01T10:00:00+00:00"


@pytest.fixture(autouse=True)
def _file_backend(monkeypatch):
    monkeypatch.delenv("JOB_STORE", raising=False)
    monkeypatch.delenv("JOB_RETENTION_DAYS", raising=False)


def _put(store, job_id, status="delivered", **extra):
    store.put({"job_id": job_id, "status": status, "created_at": CREATED, "text": "ciao", **extra})


def test_dry_run_reports_but_writes_nothing(tmp_path):
    store = FileJobStore(str(tmp_path))
    _put(store, "a1")
    counts = bf.backfill(store, apply=False)
    assert counts["missing"] == 1 and counts["updated"] == 0
    assert "expire_at" not in store.get("a1")


def test_apply_sets_expire_at_from_created_at(tmp_path):
    store = FileJobStore(str(tmp_path))
    _put(store, "a1")
    counts = bf.backfill(store, apply=True)
    assert counts["updated"] == 1
    assert store.get("a1")["expire_at"] == expiry_for(CREATED)


def test_jobs_that_have_an_expiry_are_not_touched(tmp_path):
    store = FileJobStore(str(tmp_path))
    _put(store, "a1", expire_at="2030-01-01T00:00:00+00:00")
    counts = bf.backfill(store, apply=True)
    assert counts["already_set"] == 1 and counts["updated"] == 0
    assert store.get("a1")["expire_at"] == "2030-01-01T00:00:00+00:00"


def test_every_status_is_covered_and_other_fields_survive(tmp_path):
    store = FileJobStore(str(tmp_path))
    for i, status in enumerate(["queued", "running", "needs_review", "approved", "delivered", "weird_new_status"]):
        _put(store, f"j{i}", status=status)
    counts = bf.backfill(store, apply=True)
    assert counts["updated"] == 6
    got = store.get("j5")
    assert got["status"] == "weird_new_status" and got["text"] == "ciao" and got["expire_at"]


def test_second_run_finds_nothing_to_do(tmp_path):
    store = FileJobStore(str(tmp_path))
    _put(store, "a1")
    bf.backfill(store, apply=True)
    counts = bf.backfill(store, apply=True)
    assert counts["missing"] == 0 and counts["updated"] == 0 and counts["already_set"] == 1


def test_a_job_without_created_at_still_gets_an_expiry(tmp_path):
    store = FileJobStore(str(tmp_path))
    store.put({"job_id": "old", "status": "queued", "text": "x"})
    counts = bf.backfill(store, apply=True)
    assert counts["no_created_at"] == 1 and store.get("old")["expire_at"]


def test_a_job_that_changed_status_meanwhile_is_skipped_not_overwritten(tmp_path):
    store = FileJobStore(str(tmp_path))
    _put(store, "a1", status="needs_review")
    real_transition = store.transition

    def racing(job_id, from_status, updates):
        real_transition(job_id, from_status, {"status": "approved"})  # Luigi taps Approve first
        return real_transition(job_id, from_status, updates)

    store.transition = racing
    counts = bf.backfill(store, apply=True)
    assert counts["changed_meanwhile"] == 1 and counts["updated"] == 0
    assert store.get("a1")["status"] == "approved"


def test_main_is_dry_run_unless_apply_is_given(tmp_path, capsys):
    store = FileJobStore(str(tmp_path))
    _put(store, "a1")
    assert bf.main(["--queue-dir", str(tmp_path)]) == 0
    out = capsys.readouterr().out
    assert "dry run" in out.lower() and "expire_at" not in json.dumps(store.get("a1"))
    assert bf.main(["--queue-dir", str(tmp_path), "--apply"]) == 0
    assert store.get("a1")["expire_at"]


def test_output_never_contains_what_customers_typed(tmp_path, capsys):
    store = FileJobStore(str(tmp_path))
    _put(store, "a1", text="il mio segreto personale")
    bf.main(["--queue-dir", str(tmp_path), "--apply"])
    assert "segreto" not in capsys.readouterr().out


# ── pending jobs get a fresh period, finished ones count from creation ───────

OLD = "2026-01-01T10:00:00+00:00"  # long before the retention window ends
NOW = "2026-10-09T12:00:00+00:00"


def test_a_pending_job_older_than_the_retention_gets_a_full_fresh_period(tmp_path):
    store = FileJobStore(str(tmp_path))
    for status in ("needs_review", "approved", "running", "awaiting_review", "delivering", "failed", "queued"):
        store.put({"job_id": status, "status": status, "created_at": OLD, "text": "x"})
    counts = bf.backfill(store, apply=True, now=NOW)
    assert counts["updated"] == 7
    for status in ("needs_review", "running", "failed"):
        assert store.get(status)["expire_at"] == expiry_for(NOW)  # now + retention, not OLD + retention


def test_a_finished_job_keeps_creation_plus_retention(tmp_path):
    store = FileJobStore(str(tmp_path))
    for status in ("delivered", "discarded", "rejected", "classified"):
        store.put({"job_id": status, "status": status, "created_at": OLD, "text": "x"})
    bf.backfill(store, apply=True, now=NOW)
    for status in ("delivered", "discarded", "rejected", "classified"):
        assert store.get(status)["expire_at"] == expiry_for(OLD)


def test_an_unknown_status_is_treated_as_pending(tmp_path):
    store = FileJobStore(str(tmp_path))
    store.put({"job_id": "u", "status": "brand_new_state", "created_at": OLD, "text": "x"})
    bf.backfill(store, apply=True, now=NOW)
    assert store.get("u")["expire_at"] == expiry_for(NOW)


def test_the_fresh_period_follows_the_retention_setting(tmp_path, monkeypatch):
    monkeypatch.setenv("JOB_RETENTION_DAYS", "30")
    store = FileJobStore(str(tmp_path))
    store.put({"job_id": "p", "status": "approved", "created_at": OLD, "text": "x"})
    bf.backfill(store, apply=True, now=NOW)
    assert store.get("p")["expire_at"] == "2026-11-08T12:00:00+00:00"


def test_dry_run_prints_a_per_status_breakdown_without_job_text(tmp_path, capsys):
    store = FileJobStore(str(tmp_path))
    store.put({"job_id": "a", "status": "needs_review", "created_at": OLD, "text": "dati riservati"})
    store.put({"job_id": "b", "status": "needs_review", "created_at": OLD, "text": "dati riservati"})
    store.put({"job_id": "c", "status": "delivered", "created_at": OLD, "text": "dati riservati"})
    assert bf.main(["--queue-dir", str(tmp_path)]) == 0
    out = capsys.readouterr().out
    assert "needs_review" in out and "delivered" in out and "riservati" not in out
    nr = next(l for l in out.splitlines() if "needs_review" in l)
    assert "2" in nr and "fresh" in nr
    dl = next(l for l in out.splitlines() if "delivered" in l)
    assert "1" in dl and "creation" in dl
    assert store.get("a").get("expire_at") is None


def test_apply_prints_the_breakdown_too(tmp_path, capsys):
    store = FileJobStore(str(tmp_path))
    store.put({"job_id": "a", "status": "approved", "created_at": OLD, "text": "x"})
    bf.main(["--queue-dir", str(tmp_path), "--apply"])
    out = capsys.readouterr().out
    assert "approved" in out and "fresh" in out
