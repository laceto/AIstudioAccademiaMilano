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
