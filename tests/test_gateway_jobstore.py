"""Tests for gateway/jobstore.py — where jobs live.

Jobs used to be JSON files in /tmp/queue, which Cloud Run wipes on every
restart: a needs_review job vanished before Luigi could look at it. The store
is now pluggable: files for local runs and tests, Firestore in production.
Both backends must honour the same contract.
"""

import copy
import json
import sys
from datetime import datetime, timedelta, timezone

import pytest

from gateway import jobstore
from gateway.jobstore import FileJobStore, FirestoreJobStore, make_store


# ── a minimal in-memory stand-in for the Firestore client ────────────────────


class _Snap:
    def __init__(self, data):
        self._data = data
        self.exists = data is not None

    def to_dict(self):
        return dict(self._data) if self._data is not None else None


class _Doc:
    def __init__(self, db, name, doc_id):
        self.db, self.name, self.id = db, name, doc_id

    def set(self, data):
        self.db.data.setdefault(self.name, {})[self.id] = copy.deepcopy(data)  # keeps datetimes, like Firestore

    def get(self, transaction=None):
        return _Snap(self.db.data.get(self.name, {}).get(self.id))


class _Query:
    def __init__(self, db, name, field, value):
        self.db, self.name, self.field, self.value = db, name, field, value

    def stream(self):
        for doc_id, data in self.db.data.get(self.name, {}).items():
            if data.get(self.field) == self.value:
                yield _Snap(data)


class _Coll:
    def __init__(self, db, name):
        self.db, self.name = db, name

    def document(self, doc_id):
        return _Doc(self.db, self.name, doc_id)

    def where(self, *args, filter=None, **kwargs):
        if filter is not None:  # FieldFilter(field, op, value)
            field, op, value = filter.field_path, filter.op_string, filter.value
        else:
            field, op, value = args
        assert op == "=="
        return _Query(self.db, self.name, field, value)


class _Txn:
    """Stand-in for a Firestore transaction: applies writes immediately, which is
    enough to exercise the read-check-write logic in a single process."""

    def set(self, ref, data):
        ref.set(data)


class FakeFirestore:
    def __init__(self):
        self.data = {}

    def collection(self, name):
        return _Coll(self, name)

    def transaction(self):
        return _Txn()


@pytest.fixture(params=["file", "firestore"])
def store(request, tmp_path):
    if request.param == "file":
        return FileJobStore(str(tmp_path))
    return FirestoreJobStore(client=FakeFirestore(), collection="jobs")


def _job(job_id="aaa", status="queued", created="2026-10-09T10:00:00+00:00", **extra):
    return {"job_id": job_id, "status": status, "created_at": created, "text": "caffè ☕", **extra}


# ── contract (both backends) ─────────────────────────────────────────────────


def test_put_then_get_roundtrip_keeps_unicode(store):
    store.put(_job("a1"))
    assert store.get("a1")["text"] == "caffè ☕"


def test_get_unknown_returns_none(store):
    assert store.get("nope") is None


def test_put_overwrites_same_job(store):
    store.put(_job("a1", status="queued"))
    store.put(_job("a1", status="needs_review"))
    assert store.get("a1")["status"] == "needs_review"


def test_list_by_status_filters_and_sorts_oldest_first(store):
    store.put(_job("late", created="2026-10-09T12:00:00+00:00"))
    store.put(_job("early", created="2026-10-09T08:00:00+00:00"))
    store.put(_job("other", status="needs_review"))
    assert [j["job_id"] for j in store.list_by_status("queued")] == ["early", "late"]
    assert [j["job_id"] for j in store.list_by_status("needs_review")] == ["other"]
    assert store.list_by_status("delivered") == []


def test_get_returns_a_copy(store):
    store.put(_job("a1"))
    got = store.get("a1")
    got["status"] = "tampered"
    assert store.get("a1")["status"] == "queued"


# ── file backend specifics ───────────────────────────────────────────────────


def test_file_store_keeps_the_on_disk_layout(tmp_path):
    FileJobStore(str(tmp_path)).put(_job("a1"))
    on_disk = json.loads((tmp_path / "a1.json").read_text(encoding="utf-8"))
    assert on_disk["job_id"] == "a1"


def test_file_store_skips_corrupt_files(tmp_path):
    (tmp_path / "broken.json").write_text("{not json", encoding="utf-8")
    store = FileJobStore(str(tmp_path))
    store.put(_job("ok"))
    assert [j["job_id"] for j in store.list_by_status("queued")] == ["ok"]


def test_file_store_rejects_path_traversal_ids(tmp_path):
    store = FileJobStore(str(tmp_path))
    assert store.get("../../etc/passwd") is None


# ── firestore backend specifics ──────────────────────────────────────────────


def test_firestore_store_uses_the_job_id_as_document_id():
    db = FakeFirestore()
    FirestoreJobStore(client=db, collection="jobs").put(_job("a1"))
    assert "a1" in db.data["jobs"]


def test_firestore_library_is_only_imported_when_needed(monkeypatch):
    # Importing the module must not need the library; using the real client without it
    # must fail with a clear message. A None entry in sys.modules makes the import fail.
    monkeypatch.setitem(sys.modules, "google.cloud.firestore", None)
    with pytest.raises(RuntimeError, match="google-cloud-firestore"):
        FirestoreJobStore(client=None)._collection()


# ── make_store ───────────────────────────────────────────────────────────────


def test_make_store_defaults_to_files(monkeypatch, tmp_path):
    monkeypatch.delenv("JOB_STORE", raising=False)
    assert isinstance(make_store(str(tmp_path)), FileJobStore)


def test_make_store_picks_firestore_from_env(monkeypatch, tmp_path):
    monkeypatch.setenv("JOB_STORE", "firestore")
    monkeypatch.setattr(jobstore, "_firestore_client", lambda project=None: FakeFirestore())
    jobstore._cached_firestore_store.cache_clear()
    s = make_store(str(tmp_path))
    assert isinstance(s, FirestoreJobStore)
    assert make_store(str(tmp_path)) is s  # one client per process, not one per request


def test_make_store_rejects_unknown_backend(monkeypatch, tmp_path):
    monkeypatch.setenv("JOB_STORE", "redis")
    with pytest.raises(ValueError, match="redis"):
        make_store(str(tmp_path))


# ── consumers ────────────────────────────────────────────────────────────────


def test_adapter_and_worker_share_one_store(tmp_path):
    from gateway.pipeline_adapter import PipelineAdapter
    from gateway.worker import QueueWorker

    adapter = PipelineAdapter(queue_dir=str(tmp_path))
    job_id = adapter.submit("serve un sito", "api", {})["job_id"]
    assert adapter.get_status(job_id)["status"] == "queued"
    assert [j["job_id"] for j in adapter.list_pending()] == [job_id]
    assert (adapter.queue_dir / f"{job_id}.json").exists()  # layout other code relies on

    worker = QueueWorker(queue_dir=str(tmp_path))
    assert worker.adapter.get_status(job_id)["job_id"] == job_id


def test_adapter_can_run_on_an_injected_store():
    from gateway.pipeline_adapter import PipelineAdapter

    db_store = FirestoreJobStore(client=FakeFirestore(), collection="jobs")
    adapter = PipelineAdapter(store=db_store)
    job_id = adapter.submit("serve un sito", "api", {})["job_id"]
    assert db_store.get(job_id)["text"] == "serve un sito"
    assert adapter.get_status("missing") == {"job_id": "missing", "status": "not_found", "result": None}


def test_process_job_persists_through_the_store(monkeypatch, tmp_path):
    import asyncio

    from gateway.pipeline_adapter import PipelineAdapter
    from gateway.worker import QueueWorker

    db_store = FirestoreJobStore(client=FakeFirestore(), collection="jobs")
    worker = QueueWorker(queue_dir=str(tmp_path))
    worker.adapter = PipelineAdapter(store=db_store)

    async def fake_classify(text):
        return {"product_type": "static_landing_page", "confidence": 0.95, "summary": "s", "needs_review": False}

    monkeypatch.setattr(worker, "classify", fake_classify)
    job_id = worker.adapter.submit("landing page", "api", {})["job_id"]
    job = worker.adapter.get_status(job_id)
    status, _ = asyncio.run(worker.process_job(job))

    assert status == "classified"
    saved = db_store.get(job_id)
    assert saved["status"] == "classified" and saved["classification"]["product_type"] == "static_landing_page"
    assert not list(tmp_path.glob("*.json"))  # nothing leaked to local disk


# ── transition: atomic status change (approval must happen once) ─────────────


@pytest.fixture(autouse=True)
def _fake_transactional(monkeypatch):
    # The real decorator comes from google-cloud-firestore (not installed in the tests).
    monkeypatch.setattr(jobstore, "_transactional", lambda fn: lambda txn: fn(txn))


def test_transition_applies_updates_when_status_matches(store):
    store.put(_job("a1", status="needs_review"))
    got = store.transition("a1", "needs_review", {"status": "approved", "price": 9.9})
    assert got["status"] == "approved" and got["price"] == 9.9
    assert store.get("a1")["status"] == "approved" and store.get("a1")["text"] == "caffè ☕"


def test_transition_refuses_when_status_differs(store):
    store.put(_job("a1", status="approved"))
    assert store.transition("a1", "needs_review", {"status": "rejected"}) is None
    assert store.get("a1")["status"] == "approved"


def test_transition_unknown_job_returns_none(store):
    assert store.transition("ghost", "needs_review", {"status": "approved"}) is None


def test_second_transition_loses(store):
    store.put(_job("a1", status="needs_review"))
    first = store.transition("a1", "needs_review", {"status": "approved"})
    second = store.transition("a1", "needs_review", {"status": "rejected"})
    assert first is not None and second is None
    assert store.get("a1")["status"] == "approved"


def test_transition_cannot_change_the_job_id(store):
    store.put(_job("a1", status="needs_review"))
    got = store.transition("a1", "needs_review", {"status": "approved", "job_id": "evil"})
    assert got["job_id"] == "a1" and store.get("evil") is None


def test_concurrent_file_transitions_have_a_single_winner(tmp_path):
    import threading

    store = FileJobStore(str(tmp_path))
    store.put(_job("a1", status="needs_review"))
    wins = []

    def attempt(n):
        if store.transition("a1", "needs_review", {"status": "approved", "by": n}):
            wins.append(n)

    threads = [threading.Thread(target=attempt, args=(n,)) for n in range(8)]
    [t.start() for t in threads]
    [t.join() for t in threads]
    assert len(wins) == 1


# ── expire_at: Firestore TTL needs a timestamp, the rest of the code keeps ISO strings ──

EXPIRY = "2027-01-07T10:00:00+00:00"


def test_expire_at_roundtrips_as_the_same_string_on_both_backends(store):
    store.put(_job("a1", expire_at=EXPIRY))
    assert store.get("a1")["expire_at"] == EXPIRY
    assert store.list_by_status("queued")[0]["expire_at"] == EXPIRY


def test_firestore_stores_expire_at_as_a_timezone_aware_utc_datetime():
    db = FakeFirestore()
    FirestoreJobStore(client=db, collection="jobs").put(_job("a1", expire_at=EXPIRY))
    raw = db.data["jobs"]["a1"]["expire_at"]
    assert isinstance(raw, datetime)
    assert raw.utcoffset() == timedelta(0) and raw == datetime(2027, 1, 7, 10, tzinfo=timezone.utc)


def test_firestore_converts_other_offsets_and_naive_times_to_utc():
    db = FakeFirestore()
    s = FirestoreJobStore(client=db, collection="jobs")
    s.put(_job("a1", expire_at="2027-01-07T12:00:00+02:00"))
    s.put(_job("a2", expire_at="2027-01-07T10:00:00"))  # naive counts as UTC
    assert db.data["jobs"]["a1"]["expire_at"] == datetime(2027, 1, 7, 10, tzinfo=timezone.utc)
    assert db.data["jobs"]["a2"]["expire_at"] == datetime(2027, 1, 7, 10, tzinfo=timezone.utc)
    assert s.get("a1")["expire_at"] == EXPIRY


def test_firestore_without_expire_at_adds_nothing():
    db = FakeFirestore()
    s = FirestoreJobStore(client=db, collection="jobs")
    s.put(_job("a1"))
    assert "expire_at" not in db.data["jobs"]["a1"] and "expire_at" not in s.get("a1")


def test_firestore_rejects_an_expire_at_that_is_not_a_time():
    with pytest.raises(ValueError, match="expire_at"):
        FirestoreJobStore(client=FakeFirestore(), collection="jobs").put(_job("a1", expire_at="soon"))


def test_put_does_not_modify_the_callers_job():
    job = _job("a1", expire_at=EXPIRY)
    FirestoreJobStore(client=FakeFirestore(), collection="jobs").put(job)
    assert job["expire_at"] == EXPIRY


def test_transition_returns_strings_and_keeps_the_original_expiry(store):
    store.put(_job("a1", status="needs_review", expire_at=EXPIRY))
    got = store.transition("a1", "needs_review", {"status": "approved"})
    assert got["expire_at"] == EXPIRY and store.get("a1")["expire_at"] == EXPIRY


def test_firestore_transition_writes_a_datetime_back():
    db = FakeFirestore()
    s = FirestoreJobStore(client=db, collection="jobs")
    s.put(_job("a1", status="needs_review", expire_at=EXPIRY))
    s.transition("a1", "needs_review", {"status": "approved"})
    assert isinstance(db.data["jobs"]["a1"]["expire_at"], datetime)


def test_adapter_gives_every_new_job_an_expiry_from_its_creation_time(tmp_path, monkeypatch):
    from gateway.pipeline_adapter import PipelineAdapter
    from gateway.retention import expiry_for

    monkeypatch.setenv("JOB_RETENTION_DAYS", "30")
    adapter = PipelineAdapter(queue_dir=str(tmp_path))
    job = adapter.get_status(adapter.submit("serve un sito", "api", {})["job_id"])
    assert job["expire_at"] == expiry_for(job["created_at"])
    created = datetime.fromisoformat(job["created_at"])
    assert datetime.fromisoformat(job["expire_at"]) - created == timedelta(days=30)


def test_adapter_on_firestore_stores_a_timestamp_and_reads_a_string():
    from gateway.pipeline_adapter import PipelineAdapter

    db = FakeFirestore()
    adapter = PipelineAdapter(store=FirestoreJobStore(client=db, collection="jobs"))
    job_id = adapter.submit("serve un sito", "api", {})["job_id"]
    assert isinstance(db.data["jobs"][job_id]["expire_at"], datetime)
    assert isinstance(adapter.get_status(job_id)["expire_at"], str)
