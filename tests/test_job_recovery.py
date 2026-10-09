"""A job stuck in `running` is detected, failed once, reported once, and never re-run on its own.

Covers gateway/recovery.py (sweep_stale, sweep_and_notify, finish_run), POST /sweep on the pipeline
worker, the late result of a worker that outlived the sweeper, and Luigi's /sweep and /pending.
Everything runs on a FileJobStore in tmp_path with spies instead of Telegram: no network.
"""

import asyncio
from datetime import datetime, timedelta, timezone

import pytest
from fastapi.testclient import TestClient

from gateway import admin_telegram as at
from gateway import pipeline_worker as pw
from gateway import recovery
from gateway.jobstore import FileJobStore
from gateway.studio_runner import RunResult

LUIGI = 5670736210
FRIEND = 190776580
NOW = datetime(2026, 10, 9, 12, 0, 0, tzinfo=timezone.utc)
STALE = 1200


def _iso(seconds_ago: float, now: datetime = NOW) -> str:
    return (now - timedelta(seconds=seconds_ago)).isoformat()


def _job(job_id="abc123", status="running", started=1500, **extra):
    job = {
        "job_id": job_id, "status": status, "price": 5.5, "text": "Api service to get current age",
        "channel": "telegram", "metadata": {"chat_id": str(FRIEND)}, "created_at": _iso(3600),
    }
    if started is not None:
        job["started_at"] = _iso(started)
    job.update(extra)
    return job


@pytest.fixture(autouse=True)
def _env(monkeypatch):
    monkeypatch.delenv("ADMIN_TELEGRAM_IDS", raising=False)
    monkeypatch.setenv("NOTIFY_TELEGRAM_CHAT_IDS", str(LUIGI))
    monkeypatch.delenv("PIPELINE_STALE_SECONDS", raising=False)


@pytest.fixture
def store(tmp_path):
    return FileJobStore(str(tmp_path))


def _sweep(store, **kw):
    return recovery.sweep_stale(store, now=NOW, stale_after=STALE, **kw)


# ── when is a job stale ──────────────────────────────────────────────────────


def test_a_job_just_under_the_limit_is_left_alone(store):
    store.put(_job(started=STALE - 1))
    assert _sweep(store) == []
    assert store.get("abc123")["status"] == "running"


def test_exactly_at_the_limit_is_still_alive(store):
    store.put(_job(started=STALE))
    assert _sweep(store) == []


def test_a_job_just_over_the_limit_is_failed(store):
    store.put(_job(started=STALE + 1))
    swept = _sweep(store)
    assert [j["job_id"] for j in swept] == ["abc123"]
    assert store.get("abc123")["status"] == "failed"


def test_only_running_jobs_are_touched(store):
    for status in ("needs_review", "approved", "awaiting_review", "delivering", "delivered", "failed", "rejected", "discarded"):
        store.put(_job(job_id=f"j_{status}", status=status, started=99999))
    assert _sweep(store) == []
    assert {store.get(f"j_{s}")["status"] for s in ("approved", "delivered", "failed")} == {"approved", "delivered", "failed"}


def test_the_failure_is_explained_in_italian_and_recorded(store):
    store.put(_job(started=30 * 60))
    swept = _sweep(store)[0]
    assert swept["status"] == "failed"
    assert "Interrotta" in swept["error"] and "30 minuti" in swept["error"]
    assert swept["swept_at"] == NOW.isoformat()
    assert swept["finished_at"] == NOW.isoformat()
    assert store.get("abc123")["swept_at"] == NOW.isoformat()


def test_it_never_reruns_anything(store):
    store.put(_job(started=5000))
    _sweep(store)
    assert store.get("abc123")["status"] == "failed"  # not approved: only Luigi's Riprova does that


# ── missing or garbled timestamps ────────────────────────────────────────────


def test_missing_started_at_falls_back_to_created_at(store):
    store.put(_job(started=None, created_at=_iso(STALE + 60)))
    assert len(_sweep(store)) == 1


def test_missing_started_at_with_a_recent_created_at_is_alive(store):
    store.put(_job(started=None, created_at=_iso(60)))
    assert _sweep(store) == []


def test_garbled_started_at_falls_back_to_created_at(store):
    store.put(_job(started=None, started_at="not a date", created_at=_iso(STALE + 60)))
    assert len(_sweep(store)) == 1
    store.put(_job(job_id="young", started=None, started_at=12345, created_at=_iso(60)))
    assert [j["job_id"] for j in _sweep(store)] == []


def test_nothing_parsable_at_all_counts_as_stale(store):
    store.put(_job(started=None, started_at="??", created_at="also ??"))
    swept = _sweep(store)
    assert len(swept) == 1 and "Interrotta" in swept[0]["error"]


def test_naive_timestamps_are_read_as_utc(store):
    naive = (NOW - timedelta(seconds=STALE + 60)).replace(tzinfo=None).isoformat()
    store.put(_job(started=None, started_at=naive))
    assert len(_sweep(store)) == 1


def test_a_trailing_z_is_understood(store):
    z = (NOW - timedelta(seconds=STALE + 60)).strftime("%Y-%m-%dT%H:%M:%SZ")
    store.put(_job(started=None, started_at=z))
    assert len(_sweep(store)) == 1


def test_stale_seconds_reads_the_environment(monkeypatch):
    assert recovery.stale_seconds() == 1200
    monkeypatch.setenv("PIPELINE_STALE_SECONDS", "300")
    assert recovery.stale_seconds() == 300
    for bad in ("abc", "0", "-5", ""):
        monkeypatch.setenv("PIPELINE_STALE_SECONDS", bad)
        assert recovery.stale_seconds() == 1200


# ── races ────────────────────────────────────────────────────────────────────


class FinishesFirst(FileJobStore):
    """The worker completes the job after the sweeper listed it and before it transitions."""

    def list_by_status(self, status):
        listed = super().list_by_status(status)
        for job in listed:
            self.transition(job["job_id"], "running", {"status": "awaiting_review"})
        return listed


def test_a_job_that_completes_at_the_same_moment_is_not_failed(tmp_path):
    racing = FinishesFirst(str(tmp_path))
    racing.put(_job(started=STALE + 600))
    assert recovery.sweep_stale(racing, now=NOW, stale_after=STALE) == []
    assert racing.get("abc123")["status"] == "awaiting_review"
    assert "swept_at" not in racing.get("abc123")


# ── telling Luigi, once ──────────────────────────────────────────────────────


class Spy:
    def __init__(self, boom=None):
        self.calls, self.boom = [], boom

    async def __call__(self, job, result):
        self.calls.append((job, result))
        if self.boom:
            raise self.boom
        return {"telegram": "sent"}


def test_luigi_is_told_with_the_failure_message(store):
    store.put(_job(started=STALE + 100))
    spy = Spy()
    swept = asyncio.run(recovery.sweep_and_notify(store, notify=spy, now=NOW, stale_after=STALE))
    assert [j["job_id"] for j in swept] == ["abc123"]
    (job, result), = spy.calls
    assert job["job_id"] == "abc123" and result["ok"] is False and "Interrotta" in result["error"]


def test_sweeping_twice_notifies_once(store):
    store.put(_job(started=STALE + 100))
    spy = Spy()
    asyncio.run(recovery.sweep_and_notify(store, notify=spy, now=NOW, stale_after=STALE))
    again = asyncio.run(recovery.sweep_and_notify(store, notify=spy, now=NOW + timedelta(minutes=10), stale_after=STALE))
    assert again == [] and len(spy.calls) == 1


def test_a_failing_notification_does_not_undo_the_sweep(store):
    store.put(_job(started=STALE + 100))
    swept = asyncio.run(recovery.sweep_and_notify(store, notify=Spy(boom=RuntimeError("telegram down")), now=NOW, stale_after=STALE))
    assert len(swept) == 1 and store.get("abc123")["status"] == "failed"


def test_riprova_still_works_on_a_swept_job(store, monkeypatch):
    from gateway.admin import restart_job

    store.put(_job(started=STALE + 100))
    _sweep(store)
    assert restart_job(store, "abc123", LUIGI).ok
    assert store.get("abc123")["status"] == "approved"


# ── the late result of a worker that outlived the sweeper ────────────────────


OK_UPDATES = {"status": "awaiting_review", "finished_at": "t", "result": {"ok": True, "content": "x"}, "error": None}
FAIL_UPDATES = {"status": "failed", "finished_at": "t", "result": {"ok": False}, "error": "boom"}


def test_finish_run_normal_path(store):
    job = _job(started=100)
    store.put(job)
    assert recovery.finish_run(store, job, OK_UPDATES) == "finished"
    assert store.get("abc123")["status"] == "awaiting_review"


def test_a_late_result_is_kept_when_the_sweeper_got_there_first(store):
    job = _job(started=STALE + 100)
    store.put(job)
    _sweep(store)
    assert recovery.finish_run(store, job, OK_UPDATES) == "late"
    saved = store.get("abc123")
    assert saved["status"] == "awaiting_review" and saved["result"]["content"] == "x"
    assert saved["error"] is None and saved["late_result"] is True


def test_a_late_failure_does_not_overwrite_or_renotify(store):
    job = _job(started=STALE + 100)
    store.put(job)
    _sweep(store)
    assert recovery.finish_run(store, job, FAIL_UPDATES) == "already_failed"
    assert "Interrotta" in store.get("abc123")["error"]


def test_a_late_result_never_lands_on_a_newer_run(store):
    from gateway.admin import restart_job

    old = _job(started=STALE + 100)
    store.put(old)
    _sweep(store)
    restart_job(store, "abc123", LUIGI)  # Luigi pressed Riprova
    store.transition("abc123", "approved", {"status": "running", "started_at": _iso(10)})  # the new run
    assert recovery.finish_run(store, old, OK_UPDATES) == "superseded"
    assert store.get("abc123")["status"] == "running"


def test_a_late_result_is_not_applied_after_riprova_queued_a_new_run(store):
    from gateway.admin import restart_job

    old = _job(started=STALE + 100)
    store.put(old)
    _sweep(store)
    restart_job(store, "abc123", LUIGI)  # approved again, waiting in the queue
    assert recovery.finish_run(store, old, OK_UPDATES) == "lost"
    assert store.get("abc123")["status"] == "approved"


def test_a_failed_job_that_was_not_swept_is_not_resurrected(store):
    job = _job(status="failed", started=STALE + 100, error="real failure")
    store.put(job)
    assert recovery.finish_run(store, job, OK_UPDATES) == "lost"
    assert store.get("abc123")["status"] == "failed"


# ── POST /sweep and /run on the worker ───────────────────────────────────────


@pytest.fixture
def wenv(monkeypatch, tmp_path):
    monkeypatch.setenv("JOB_STORE", "file")
    monkeypatch.setenv("GATEWAY_QUEUE_DIR", str(tmp_path))
    monkeypatch.delenv("PIPELINE_RUN_TIMEOUT", raising=False)
    return FileJobStore(str(tmp_path))


@pytest.fixture
def wsent(monkeypatch):
    spy = Spy()
    monkeypatch.setattr(pw, "notify_result", spy)
    return spy.calls


def _real_job(job_id="abc123", **kw):
    """started_at relative to the real clock: the endpoint uses datetime.now."""
    return _job(job_id=job_id, **kw) | {"started_at": (datetime.now(timezone.utc) - timedelta(seconds=kw.get("started", 1500) or 0)).isoformat()}


def test_the_worker_sweeps_and_reports(wenv, wsent):
    wenv.put(_real_job(started=STALE + 600))
    wenv.put(_real_job(job_id="alive", started=60))
    client = TestClient(pw.app)
    body = client.post("/sweep").json()
    assert body == {"swept": ["abc123"]}
    assert wenv.get("abc123")["status"] == "failed" and wenv.get("alive")["status"] == "running"
    assert len(wsent) == 1
    assert client.post("/sweep").json() == {"swept": []}
    assert len(wsent) == 1


def test_sweep_on_an_empty_store_is_a_quiet_200(wenv, wsent):
    res = TestClient(pw.app).post("/sweep")
    assert res.status_code == 200 and res.json() == {"swept": []} and wsent == []


def test_sweep_is_post_only(wenv, wsent):
    assert TestClient(pw.app).get("/sweep").status_code == 405


class SweepsMidRun:
    """A pipeline run that the sweeper declares dead while it is still working."""

    def __init__(self, store, result):
        self.store, self.result = store, result

    def __call__(self, job, *, provider="openai"):
        recovery.sweep_stale(self.store, now=datetime.now(timezone.utc) + timedelta(hours=1), stale_after=STALE)
        return self.result


def _approved():
    return {"job_id": "abc123", "status": "approved", "price": 5.5, "text": "t", "channel": "telegram",
            "metadata": {"chat_id": str(FRIEND)}, "created_at": _iso(3600)}


def test_the_worker_keeps_a_paid_result_the_sweeper_gave_up_on(wenv, wsent, monkeypatch):
    ok = RunResult(ok=True, filename="a.py", content="print(1)", product_type="unknown_product", price=5.5,
                   invoice_id="INV-1", qa_passed=True, risk_score=1.0, steps=[])
    monkeypatch.setattr(pw, "run_job", SweepsMidRun(wenv, ok))
    wenv.put(_approved())
    body = TestClient(pw.app).post("/run", json={"job_id": "abc123"}).json()
    saved = wenv.get("abc123")
    assert body == {"status": "awaiting_review"} and saved["status"] == "awaiting_review"
    assert saved["result"]["content"] == "print(1)" and saved["late_result"] is True
    assert wsent[-1][1]["ok"] is True  # Luigi gets the file with Invia / Scarta


def test_a_run_that_fails_after_the_sweep_does_not_notify_twice(wenv, wsent, monkeypatch):
    monkeypatch.setattr(pw, "run_job", SweepsMidRun(wenv, RunResult(ok=False, error="boom")))
    wenv.put(_approved())
    # the sweep inside run_job notifies nothing (sweep_stale is sync); the worker must stay quiet too
    TestClient(pw.app).post("/run", json={"job_id": "abc123"})
    assert wenv.get("abc123")["status"] == "failed" and "Interrotta" in wenv.get("abc123")["error"]
    assert wsent == []


# ── Luigi's /sweep and /pending ──────────────────────────────────────────────


class FakeBot:
    def __init__(self):
        self.sent = []

    async def send_message(self, chat_id, text, **kw):
        self.sent.append((chat_id, text, kw))

    def to(self, chat_id):
        return [t for c, t, _ in self.sent if c == chat_id]


def _msg(text, from_id=LUIGI):
    return {"message_id": 5, "from": {"id": from_id}, "chat": {"id": from_id}, "text": text}


def _live(job_id, seconds, **kw):
    now = datetime.now(timezone.utc)
    return _job(job_id=job_id, started=None, **kw) | {"started_at": (now - timedelta(seconds=seconds)).isoformat()}


@pytest.fixture
def tg(monkeypatch, store):
    spy = Spy()
    monkeypatch.setattr(at, "notify_result", spy)
    return FakeBot(), spy


def test_luigi_sweeps_by_command(store, tg):
    bot, spy = tg
    store.put(_live("old", STALE + 600))
    store.put(_live("young", 60))
    assert asyncio.run(at.handle_admin_message(bot, store, _msg("/sweep"))) is True
    assert store.get("old")["status"] == "failed" and store.get("young")["status"] == "running"
    assert len(spy.calls) == 1
    reply = " ".join(bot.to(LUIGI))
    assert "old" in reply and "young" not in reply


def test_sweep_with_nothing_stuck_says_so(store, tg):
    bot, spy = tg
    store.put(_live("young", 60))
    asyncio.run(at.handle_admin_message(bot, store, _msg("/sweep")))
    assert "Nessun job fermo" in " ".join(bot.to(LUIGI)) and spy.calls == []


def test_a_strangers_sweep_is_swallowed(store, tg):
    bot, spy = tg
    store.put(_live("old", STALE + 600))
    assert asyncio.run(at.handle_admin_message(bot, store, _msg("/sweep", from_id=FRIEND))) is True
    assert bot.to(FRIEND) == ["Comando non disponibile."]
    assert store.get("old")["status"] == "running" and spy.calls == []


def test_a_forged_update_cannot_sweep_either(store, tg):
    bot, _ = tg
    assert asyncio.run(at.refuse_admin_command(bot, _msg("/sweep", from_id=FRIEND))) is True
    assert bot.to(FRIEND) == ["Comando non disponibile."]


def test_sweep_is_in_the_usage_text():
    assert "/sweep" in at._USAGE and "/sweep" in at._COMMANDS


def test_pending_lists_running_jobs_with_their_age_and_flags_the_stale_one(store, tg):
    bot, _ = tg
    store.put(_live("fresh", 5 * 60))
    store.put(_live("stuck", STALE + 10 * 60))
    asyncio.run(at.handle_admin_message(bot, store, _msg("/pending")))
    texts = {t.split()[2] if False else t: t for t in bot.to(LUIGI)}
    fresh = next(t for t in texts if "fresh" in t)
    stuck = next(t for t in texts if "stuck" in t)
    assert "5 min" in fresh and "FERMO" not in fresh
    assert "30 min" in stuck and "FERMO" in stuck and "/sweep" in stuck


def test_pending_with_only_running_jobs_is_not_empty(store, tg):
    bot, _ = tg
    store.put(_live("fresh", 60))
    asyncio.run(at.handle_admin_message(bot, store, _msg("/pending")))
    assert "Nessuna richiesta in attesa" not in " ".join(bot.to(LUIGI))
