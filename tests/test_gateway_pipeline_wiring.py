"""Approving a job starts the pipeline; a failed run can be restarted — and nothing else does.

Covers gateway/admin.py::restart_job and the hooks in gateway/admin_telegram.py. The queue is
replaced by a spy: no Cloud Tasks, no network.
"""

import asyncio

import pytest

from gateway import admin
from gateway import admin_telegram as at
from gateway.jobstore import FileJobStore
from gateway.pipeline_queue import EnqueueResult

LUIGI = 5670736210
FRIEND = 190776580


class FakeBot:
    def __init__(self):
        self.sent, self.answered, self.edited = [], [], []

    async def send_message(self, chat_id, text, **kw):
        self.sent.append((chat_id, text, kw))

    async def answer_callback_query(self, callback_query_id, text=None, show_alert=False, **kw):
        self.answered.append((callback_query_id, text, show_alert))

    async def edit_message_text(self, chat_id, message_id, text, **kw):
        self.edited.append((chat_id, message_id, text, kw))

    def to(self, chat_id):
        return [t for c, t, _ in self.sent if c == chat_id]


class Queue:
    def __init__(self, result=None):
        self.calls, self.result = [], result or EnqueueResult(True, "queued")

    def __call__(self, job_id):
        self.calls.append(job_id)
        return self.result


@pytest.fixture(autouse=True)
def _env(monkeypatch):
    monkeypatch.delenv("ADMIN_TELEGRAM_IDS", raising=False)
    monkeypatch.setenv("NOTIFY_TELEGRAM_CHAT_IDS", str(LUIGI))


@pytest.fixture
def queue(monkeypatch):
    q = Queue()
    monkeypatch.setattr(at, "enqueue_run", q)
    return q


def _job(job_id="abc123", status="needs_review", product="static_landing_page"):
    return {
        "job_id": job_id, "status": status, "channel": "telegram", "text": "voglio un sito",
        "metadata": {"chat_id": str(FRIEND)}, "created_at": "2026-10-09T10:00:00+00:00",
        "classification": {"product_type": product, "confidence": 0.5, "summary": "un sito"},
    }


@pytest.fixture
def store(tmp_path):
    s = FileJobStore(str(tmp_path))
    s.put(_job())
    return s


def _cb(data, from_id=LUIGI):
    return {"id": "cb1", "from": {"id": from_id}, "data": data,
            "message": {"message_id": 7, "chat": {"id": LUIGI}, "text": "card\nJob ID: abc123"}}


def _msg(text, from_id=LUIGI, reply_to=None):
    m = {"message_id": 5, "from": {"id": from_id}, "chat": {"id": from_id}, "text": text}
    if reply_to:
        m["reply_to_message"] = {"message_id": 4, "text": reply_to}
    return m


def _run(coro):
    return asyncio.run(coro)


# ── restart_job ──────────────────────────────────────────────────────────────


def test_a_failed_job_goes_back_to_approved(store):
    store.transition("abc123", "needs_review", {"status": "failed", "error": "QA non superata", "price": 9.9})
    d = admin.restart_job(store, "abc123", LUIGI)
    assert d.ok and d.code == "restarted"
    job = store.get("abc123")
    assert job["status"] == "approved" and job["price"] == 9.9 and job["error"] is None
    assert job["restarted_by"] == str(LUIGI)


def test_an_approved_job_can_be_requeued_as_is(store):
    store.transition("abc123", "needs_review", {"status": "approved", "price": 1.0})
    assert admin.restart_job(store, "abc123", LUIGI).ok
    assert store.get("abc123")["status"] == "approved"


@pytest.mark.parametrize("status", ["needs_review", "running", "awaiting_review", "delivered", "discarded", "rejected"])
def test_other_states_cannot_be_restarted(store, status):
    store.transition("abc123", "needs_review", {"status": status})
    d = admin.restart_job(store, "abc123", LUIGI)
    assert not d.ok and d.code == "not_restartable" and store.get("abc123")["status"] == status


def test_a_stranger_cannot_restart(store):
    store.transition("abc123", "needs_review", {"status": "failed"})
    assert admin.restart_job(store, "abc123", FRIEND).code == "forbidden"
    assert store.get("abc123")["status"] == "failed"


def test_restarting_an_unknown_job(store):
    assert admin.restart_job(store, "ghost", LUIGI).code == "not_found"


# ── approving starts the pipeline ────────────────────────────────────────────


def test_the_approve_button_queues_the_job(store, queue):
    bot = FakeBot()
    _run(at.handle_callback(bot, store, _cb("ap:abc123")))
    assert queue.calls == ["abc123"]
    assert any("pipeline avviata" in t.lower() for t in bot.to(LUIGI))


def test_the_free_button_queues_the_job(store, queue):
    _run(at.handle_callback(FakeBot(), store, _cb("fr:abc123")))
    assert queue.calls == ["abc123"]


def test_rejecting_never_queues(store, queue):
    _run(at.handle_callback(FakeBot(), store, _cb("rj:abc123")))
    assert queue.calls == []


def test_a_stranger_pressing_approve_queues_nothing(store, queue):
    _run(at.handle_callback(FakeBot(), store, _cb("ap:abc123", from_id=FRIEND)))
    assert queue.calls == []


def test_a_second_press_does_not_queue_again(store, queue):
    _run(at.handle_callback(FakeBot(), store, _cb("ap:abc123")))
    _run(at.handle_callback(FakeBot(), store, _cb("ap:abc123")))
    assert queue.calls == ["abc123"]


def test_the_approve_command_queues(store, queue):
    _run(at.handle_admin_message(FakeBot(), store, _msg("/approve abc123 14,90")))
    assert queue.calls == ["abc123"]


def test_a_price_answer_queues(store, queue):
    prompt = at.PRICE_PROMPT.format(job_id="abc123")
    _run(at.handle_admin_message(FakeBot(), store, _msg("12,50", reply_to=prompt)))
    assert queue.calls == ["abc123"]


def test_a_queue_failure_keeps_the_approval_and_says_how_to_retry(store, monkeypatch):
    q = Queue(EnqueueResult(False, "PermissionDenied"))
    monkeypatch.setattr(at, "enqueue_run", q)
    bot = FakeBot()
    _run(at.handle_callback(bot, store, _cb("ap:abc123")))
    assert store.get("abc123")["status"] == "approved"
    text = " ".join(bot.to(LUIGI))
    assert "non sono riuscito ad avviare" in text.lower() and "/run abc123" in text and "PermissionDenied" in text


def test_an_unconfigured_queue_is_explained(store, monkeypatch):
    monkeypatch.setattr(at, "enqueue_run", Queue(EnqueueResult(False, "not_configured")))
    bot = FakeBot()
    _run(at.handle_callback(bot, store, _cb("ap:abc123")))
    assert any("non è configurata" in t for t in bot.to(LUIGI))


# ── /run and the retry button ────────────────────────────────────────────────


def test_run_command_restarts_a_failed_job(store, queue):
    store.transition("abc123", "needs_review", {"status": "failed", "price": 9.9})
    bot = FakeBot()
    assert _run(at.handle_admin_message(bot, store, _msg("/run abc123")))
    assert store.get("abc123")["status"] == "approved" and queue.calls == ["abc123"]


def test_run_command_refuses_a_job_that_cannot_restart(store, queue):
    store.transition("abc123", "needs_review", {"status": "running"})
    bot = FakeBot()
    _run(at.handle_admin_message(bot, store, _msg("/run abc123")))
    assert queue.calls == [] and any("non si può riavviare" in t.lower() for t in bot.to(LUIGI))


def test_run_command_usage(store, queue):
    bot = FakeBot()
    _run(at.handle_admin_message(bot, store, _msg("/run")))
    assert "uso" in bot.to(LUIGI)[0].lower() and "/run" in bot.to(LUIGI)[0]


def test_a_strangers_run_command_is_swallowed(store, queue):
    store.transition("abc123", "needs_review", {"status": "failed"})
    bot = FakeBot()
    assert _run(at.handle_admin_message(bot, store, _msg("/run abc123", from_id=FRIEND))) is True
    assert queue.calls == [] and store.get("abc123")["status"] == "failed"


def test_the_retry_button_restarts(store, queue):
    store.transition("abc123", "needs_review", {"status": "failed", "price": 9.9})
    bot = FakeBot()
    _run(at.handle_callback(bot, store, _cb("rn:abc123")))
    assert store.get("abc123")["status"] == "approved" and queue.calls == ["abc123"]
    assert bot.answered[0][1]


def test_the_retry_button_from_a_stranger_does_nothing(store, queue):
    store.transition("abc123", "needs_review", {"status": "failed"})
    _run(at.handle_callback(FakeBot(), store, _cb("rn:abc123", from_id=FRIEND)))
    assert queue.calls == [] and store.get("abc123")["status"] == "failed"


# ── actions this PR does not implement yet must not fall through to "approve" ─


@pytest.mark.parametrize("data", ["sd:abc123", "dc:abc123"])
def test_review_buttons_are_not_mistaken_for_an_approval(store, queue, data):
    bot = FakeBot()
    _run(at.handle_callback(bot, store, _cb(data)))
    assert store.get("abc123")["status"] == "needs_review" and queue.calls == []
    assert bot.answered
