"""Luigi reviews a finished pipeline result, then sends it to the customer or discards it.

Sending is the one step that reaches a third party, so it happens once (claim first, send
second), nothing reaches the customer without Luigi's button, and a failed send puts the result
back so he can try again.
"""

import asyncio

import pytest

from gateway import admin
from gateway import admin_telegram as at
from gateway.jobstore import FileJobStore

LUIGI = 5670736210
FRIEND = 190776580


class FakeBot:
    def __init__(self, fail_documents_for=()):
        self.sent, self.docs, self.answered, self.markup_edits = [], [], [], []
        self.fail_documents_for = set(fail_documents_for)

    async def send_message(self, chat_id, text, **kw):
        self.sent.append((chat_id, text, kw))

    async def send_document(self, chat_id, document, caption=None, filename=None, **kw):
        if chat_id in self.fail_documents_for:
            raise RuntimeError("Forbidden: bot was blocked by the user")
        self.docs.append({"chat_id": chat_id, "document": document, "caption": caption, "filename": filename})

    async def answer_callback_query(self, callback_query_id, text=None, show_alert=False, **kw):
        self.answered.append((callback_query_id, text, show_alert))

    async def edit_message_reply_markup(self, chat_id, message_id, reply_markup=None, **kw):
        self.markup_edits.append((chat_id, message_id, reply_markup))

    def to(self, chat_id):
        return [t for c, t, _ in self.sent if c == chat_id]


@pytest.fixture(autouse=True)
def _env(monkeypatch):
    monkeypatch.delenv("ADMIN_TELEGRAM_IDS", raising=False)
    monkeypatch.setenv("NOTIFY_TELEGRAM_CHAT_IDS", str(LUIGI))


def _job(job_id="abc123", status="awaiting_review", channel="telegram", chat=str(FRIEND)):
    return {
        "job_id": job_id, "status": status, "channel": channel, "text": "Api service to get current age",
        "price": 5.5, "metadata": {"chat_id": chat}, "created_at": "2026-10-09T10:00:00+00:00",
        "classification": {"product_type": "unknown_product", "summary": "age api"},
        "result": {
            "ok": True, "filename": "age_api.py", "content": "print('eta')\n", "price": 5.5,
            "invoice_id": "INV-1", "qa_passed": True, "risk_score": 4.5, "high_risk": True,
            "product_type": "unknown_product", "steps": [],
        },
    }


@pytest.fixture
def store(tmp_path):
    s = FileJobStore(str(tmp_path))
    s.put(_job())
    return s


def _cb(data, from_id=LUIGI):
    return {"id": "cb1", "from": {"id": from_id}, "data": data,
            "message": {"message_id": 9, "chat": {"id": LUIGI}, "caption": "Risultato pronto - job abc123"}}


def _msg(text, from_id=LUIGI):
    return {"message_id": 5, "from": {"id": from_id}, "chat": {"id": from_id}, "text": text}


def _run(coro):
    return asyncio.run(coro)


# ── the state machine ────────────────────────────────────────────────────────


def test_begin_delivery_claims_the_result(store):
    d = admin.begin_delivery(store, "abc123", LUIGI)
    assert d.ok and d.code == "delivering" and store.get("abc123")["status"] == "delivering"


@pytest.mark.parametrize("status", ["needs_review", "approved", "running", "failed", "rejected"])
def test_only_a_finished_result_can_be_sent(store, status):
    store.transition("abc123", "awaiting_review", {"status": status})
    d = admin.begin_delivery(store, "abc123", LUIGI)
    assert not d.ok and d.code == "not_reviewable" and store.get("abc123")["status"] == status


@pytest.mark.parametrize("status", ["delivering", "delivered", "discarded"])
def test_a_result_already_handled_is_not_sent_again(store, status):
    store.transition("abc123", "awaiting_review", {"status": status})
    d = admin.begin_delivery(store, "abc123", LUIGI)
    assert not d.ok and d.code == "already_handled"


def test_a_stranger_cannot_claim_a_delivery(store):
    assert admin.begin_delivery(store, "abc123", FRIEND).code == "forbidden"
    assert store.get("abc123")["status"] == "awaiting_review"


def test_unknown_job_for_delivery(store):
    assert admin.begin_delivery(store, "ghost", LUIGI).code == "not_found"


def test_finish_delivery_records_who_and_when(store):
    admin.begin_delivery(store, "abc123", LUIGI)
    job = admin.finish_delivery(store, "abc123", LUIGI)
    assert job["status"] == "delivered" and job["delivered_by"] == str(LUIGI) and job["delivered_at"]


def test_abort_delivery_puts_the_result_back_with_the_reason(store):
    admin.begin_delivery(store, "abc123", LUIGI)
    admin.abort_delivery(store, "abc123", "RuntimeError")
    job = store.get("abc123")
    assert job["status"] == "awaiting_review" and job["delivery_error"] == "RuntimeError"
    assert admin.begin_delivery(store, "abc123", LUIGI).ok  # and it can be tried again


def test_discard(store):
    d = admin.discard_result(store, "abc123", LUIGI, reason="non adatto")
    assert d.ok and d.code == "discarded"
    job = store.get("abc123")
    assert job["status"] == "discarded" and job["decision"]["reason"] == "non adatto" and job["decision"]["by"] == str(LUIGI)


def test_discard_is_for_luigi_only_and_only_once(store):
    assert admin.discard_result(store, "abc123", FRIEND).code == "forbidden"
    assert admin.discard_result(store, "abc123", LUIGI).ok
    assert admin.discard_result(store, "abc123", LUIGI).code == "already_handled"


def test_a_delivered_result_cannot_be_discarded(store):
    admin.begin_delivery(store, "abc123", LUIGI)
    admin.finish_delivery(store, "abc123", LUIGI)
    assert admin.discard_result(store, "abc123", LUIGI).code == "already_handled"
    assert store.get("abc123")["status"] == "delivered"


def test_the_customer_caption_leaves_out_internal_details():
    caption = admin.customer_caption(_job())
    assert "abc123" in caption and "5.50" in caption and "INV-1" in caption
    for internal in ("QA", "rischio", "RISCHIO", "risk", "4.5"):
        assert internal not in caption


def test_the_caption_for_a_free_job():
    job = _job()
    job["price"] = 0.0
    assert "gratuit" in admin.customer_caption(job).lower()


# ── Telegram: Invia al cliente ───────────────────────────────────────────────


def test_send_delivers_the_file_to_the_customer_once(store):
    bot = FakeBot()
    _run(at.handle_callback(bot, store, _cb("sd:abc123")))
    assert len(bot.docs) == 1
    doc = bot.docs[0]
    assert doc["chat_id"] == FRIEND and doc["filename"] == "age_api.py" and doc["document"] == b"print('eta')\n"
    assert "abc123" in doc["caption"] and "RISCHIO" not in doc["caption"]
    job = store.get("abc123")
    assert job["status"] == "delivered" and job["delivered_by"] == str(LUIGI)
    assert any("inviato" in t.lower() for t in bot.to(LUIGI))
    assert bot.markup_edits == [(LUIGI, 9, None)]  # buttons removed from the review card


def test_pressing_send_twice_sends_one_document(store):
    bot = FakeBot()
    _run(at.handle_callback(bot, store, _cb("sd:abc123")))
    _run(at.handle_callback(bot, store, _cb("sd:abc123")))
    assert len(bot.docs) == 1 and "già" in bot.answered[1][1].lower()


def test_a_stranger_pressing_send_sends_nothing(store):
    bot = FakeBot()
    _run(at.handle_callback(bot, store, _cb("sd:abc123", from_id=FRIEND)))
    assert bot.docs == [] and store.get("abc123")["status"] == "awaiting_review"


def test_a_failed_send_keeps_the_result_for_another_try(store):
    bot = FakeBot(fail_documents_for={FRIEND})
    _run(at.handle_callback(bot, store, _cb("sd:abc123")))
    job = store.get("abc123")
    assert job["status"] == "awaiting_review" and "RuntimeError" in job["delivery_error"]
    assert any("non sono riuscito a inviare" in t.lower() for t in bot.to(LUIGI))
    assert bot.markup_edits == []  # buttons stay so he can press again
    bot.fail_documents_for.clear()
    _run(at.handle_callback(bot, store, _cb("sd:abc123")))
    assert store.get("abc123")["status"] == "delivered" and len(bot.docs) == 1


def test_a_customer_not_on_telegram_is_not_sent_to(tmp_path):
    s = FileJobStore(str(tmp_path))
    s.put(_job(channel="api", chat=""))
    bot = FakeBot()
    _run(at.handle_callback(bot, s, _cb("sd:abc123")))
    assert bot.docs == [] and s.get("abc123")["status"] == "awaiting_review"
    assert any("telegram" in t.lower() for t in bot.to(LUIGI))


def test_a_result_without_content_is_not_sent(tmp_path):
    s = FileJobStore(str(tmp_path))
    broken = _job()
    broken["result"]["content"] = ""
    s.put(broken)
    bot = FakeBot()
    _run(at.handle_callback(bot, s, _cb("sd:abc123")))
    assert bot.docs == [] and s.get("abc123")["status"] == "awaiting_review"


# ── Telegram: Scarta ─────────────────────────────────────────────────────────


def test_discard_tells_luigi_and_not_the_customer(store):
    bot = FakeBot()
    _run(at.handle_callback(bot, store, _cb("dc:abc123")))
    assert store.get("abc123")["status"] == "discarded"
    assert bot.docs == [] and bot.to(FRIEND) == []
    assert any("cliente non" in t.lower() for t in bot.to(LUIGI))
    assert bot.markup_edits == [(LUIGI, 9, None)]


def test_send_after_discard_is_refused(store):
    bot = FakeBot()
    _run(at.handle_callback(bot, store, _cb("dc:abc123")))
    _run(at.handle_callback(bot, store, _cb("sd:abc123")))
    assert bot.docs == [] and store.get("abc123")["status"] == "discarded"


def test_a_stranger_cannot_discard(store):
    _run(at.handle_callback(FakeBot(), store, _cb("dc:abc123", from_id=FRIEND)))
    assert store.get("abc123")["status"] == "awaiting_review"


# ── /pending shows results and failures too; /file resends the file ──────────


def test_pending_lists_results_waiting_for_review(store):
    bot = FakeBot()
    _run(at.handle_admin_message(bot, store, _msg("/pending")))
    assert any("abc123" in t for t in bot.to(LUIGI))
    kb = [kw.get("reply_markup") for _, _, kw in bot.sent if kw.get("reply_markup")]
    assert kb  # buttons present


def test_pending_lists_failed_runs_with_a_retry_button(tmp_path):
    s = FileJobStore(str(tmp_path))
    failed = _job(status="failed")
    failed["error"] = "QA non superata"
    s.put(failed)
    bot = FakeBot()
    _run(at.handle_admin_message(bot, s, _msg("/pending")))
    text = " ".join(bot.to(LUIGI))
    assert "abc123" in text and "QA non superata" in text


def test_pending_says_so_when_there_is_nothing(tmp_path):
    bot = FakeBot()
    _run(at.handle_admin_message(bot, FileJobStore(str(tmp_path)), _msg("/pending")))
    assert "nessuna" in bot.to(LUIGI)[0].lower()


def test_file_command_resends_the_result_to_luigi(store, monkeypatch):
    seen = []

    async def spy(job, result):
        seen.append((job["job_id"], result["filename"]))
        return {"telegram": "sent"}

    monkeypatch.setattr(at, "notify_result", spy)
    assert _run(at.handle_admin_message(FakeBot(), store, _msg("/file abc123")))
    assert seen == [("abc123", "age_api.py")]


@pytest.mark.parametrize("status", ["needs_review", "approved", "running", "delivered", "discarded"])
def test_file_command_only_for_results_awaiting_review(store, monkeypatch, status):
    async def spy(job, result):
        raise AssertionError("nothing should be sent")

    monkeypatch.setattr(at, "notify_result", spy)
    store.transition("abc123", "awaiting_review", {"status": status})
    bot = FakeBot()
    _run(at.handle_admin_message(bot, store, _msg("/file abc123")))
    assert any("nessun risultato" in t.lower() for t in bot.to(LUIGI))


def test_file_command_is_for_luigi_only(store, monkeypatch):
    async def spy(job, result):
        raise AssertionError("nothing should be sent")

    monkeypatch.setattr(at, "notify_result", spy)
    bot = FakeBot()
    assert _run(at.handle_admin_message(bot, store, _msg("/file abc123", from_id=FRIEND))) is True
    assert any("non disponibile" in t.lower() for t in bot.to(FRIEND))
