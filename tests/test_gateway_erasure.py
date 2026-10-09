"""Tests for gateway/erasure.py and the /cancella flow in gateway/admin_telegram.py.

Luigi asks to erase a customer's data; he sees a card (no customer text), presses Conferma, and only
then are the jobs deleted. Busy jobs are never touched. Each erasure leaves a record without
personal data.
"""

import asyncio
import json

import pytest

from gateway import admin
from gateway import admin_telegram as at
from gateway import erasure
from gateway.jobstore import FileJobStore, FirestoreJobStore
from test_gateway_jobstore import FakeFirestore

LUIGI = 5670736210
FRIEND = 190776580
STRANGER = 777
SECRET_TEXT = "il mio IBAN IT60X0542811101000000123456 e la mia malattia"
GROUP = "-1001234567890"


class FakeBot:
    def __init__(self):
        self.sent, self.answered, self.edited = [], [], []

    async def send_message(self, chat_id, text, **kw):
        self.sent.append((chat_id, text, kw))

    async def answer_callback_query(self, callback_query_id, text=None, show_alert=False, **kw):
        self.answered.append((callback_query_id, text, show_alert))

    async def edit_message_text(self, chat_id, message_id, text, **kw):
        self.edited.append((chat_id, message_id, text, kw))

    def texts(self):
        return [t for _, t, _ in self.sent]


@pytest.fixture(autouse=True)
def _env(monkeypatch, tmp_path):
    monkeypatch.delenv("ADMIN_TELEGRAM_IDS", raising=False)
    monkeypatch.setenv("NOTIFY_TELEGRAM_CHAT_IDS", str(LUIGI))
    monkeypatch.setenv("JOB_STORE", "file")
    monkeypatch.setenv("ERASURE_DIR", str(tmp_path / "erasures"))


def _job(job_id, chat=FRIEND, status="delivered", created="2026-10-09T10:00:00+00:00"):
    return {
        "job_id": job_id, "status": status, "channel": "telegram", "text": SECRET_TEXT,
        "metadata": {"chat_id": str(chat)}, "created_at": created,
        "classification": {"product_type": "static_landing_page", "summary": SECRET_TEXT},
        "result": {"filename": "x.html", "content": SECRET_TEXT},
    }


@pytest.fixture
def store(tmp_path):
    s = FileJobStore(str(tmp_path / "queue"))
    s.put(_job("j1", status="delivered"))
    s.put(_job("j2", status="rejected", created="2026-10-10T10:00:00+00:00"))
    s.put(_job("other", chat=424242))
    s.put(_job("g1", chat=GROUP))
    return s


def _run(coro):
    return asyncio.run(coro)


def _msg(text, from_id=LUIGI):
    return {"text": text, "from": {"id": from_id}, "chat": {"id": from_id}}


def _cb(data, from_id=LUIGI):
    return {"id": "cb1", "from": {"id": from_id}, "data": data,
            "message": {"message_id": 9, "chat": {"id": from_id}, "text": "card"}}


def _records():
    return erasure.make_erasure_log().all()


def _ids(store):
    return sorted(j["job_id"] for j in store.all_jobs())


# ── erasure.py ───────────────────────────────────────────────────────────────


def test_jobs_for_chat_compares_text_and_negative_ids(store):
    assert [j["job_id"] for j in erasure.jobs_for_chat(store, FRIEND)] == ["j1", "j2"]
    assert [j["job_id"] for j in erasure.jobs_for_chat(store, str(FRIEND))] == ["j1", "j2"]
    assert [j["job_id"] for j in erasure.jobs_for_chat(store, GROUP)] == ["g1"]
    assert erasure.jobs_for_chat(store, 1) == []


@pytest.mark.parametrize("status", ["running", "delivering"])
def test_busy_jobs_are_refused_not_deleted(store, status):
    store.put(_job("busy", status=status))
    result = erasure.erase_jobs(store, ["busy", "j1"], LUIGI)
    assert result.refused == [("busy", status)]
    assert result.deleted == ["j1"]
    assert store.get("busy") is not None
    assert "/sweep" in erasure.result_message(result)


def test_status_is_rechecked_at_deletion_time(store):
    store.put(_job("late", status="awaiting_review"))
    shown = store.get("late")  # the card was built while it was deletable
    assert shown["status"] == "awaiting_review"
    store.transition("late", "awaiting_review", {"status": "delivering"})  # a worker picks it up
    result = erasure.erase_jobs(store, ["late"], LUIGI)
    assert result.deleted == [] and result.refused == [("late", "delivering")]
    assert store.get("late") is not None


def test_erase_twice_is_harmless(store):
    first = erasure.erase_jobs(store, ["j1"], LUIGI)
    second = erasure.erase_jobs(store, ["j1"], LUIGI)
    assert first.deleted == ["j1"]
    assert second.deleted == [] and second.missing == ["j1"]
    assert "gia' cancellati" in erasure.result_message(second)


def test_non_admin_cannot_erase(store):
    result = erasure.erase_jobs(store, ["j1"], STRANGER)
    assert not result.ok and store.get("j1") is not None
    assert not erasure.erase_chat(store, FRIEND, STRANGER).ok
    assert len(store.all_jobs()) == 4


def test_record_has_no_chat_id_text_or_result(store):
    result = erasure.erase_chat(store, FRIEND, LUIGI)
    assert erasure.record_erasure(erasure.make_erasure_log(), LUIGI, "chat", result)
    (rec,) = _records()
    assert set(rec) == {"at", "by", "scope", "count", "job_ids"}
    assert rec["by"] == str(LUIGI) and rec["scope"] == "chat" and rec["count"] == 2
    assert rec["job_ids"] == ["j1", "j2"]
    blob = json.dumps(rec)
    assert str(FRIEND) not in blob and "IBAN" not in blob and "malattia" not in blob


def test_record_on_firestore_backend(monkeypatch):
    fake = FakeFirestore()
    log = erasure.FirestoreErasureLog(client=fake, collection="erasures")
    jobs = FirestoreJobStore(client=fake, collection="jobs")
    jobs.put(_job("f1"))
    result = erasure.erase_jobs(jobs, ["f1"], LUIGI)
    erasure.record_erasure(log, LUIGI, "job", result)
    (doc,) = fake.data["erasures"].values()
    assert doc["job_ids"] == ["f1"] and doc["scope"] == "job"
    assert str(FRIEND) not in json.dumps(doc) and "IBAN" not in json.dumps(doc)
    assert jobs.get("f1") is None


def test_make_erasure_log_follows_job_store(monkeypatch):
    assert isinstance(erasure.make_erasure_log(), erasure.FileErasureLog)
    monkeypatch.setenv("JOB_STORE", "firestore")
    assert isinstance(erasure.make_erasure_log(), erasure.FirestoreErasureLog)
    monkeypatch.setenv("JOB_STORE", "nope")
    with pytest.raises(ValueError):
        erasure.make_erasure_log()


def test_nothing_deleted_writes_no_record(store):
    result = erasure.erase_jobs(store, ["ghost"], LUIGI)
    erasure.record_erasure(erasure.make_erasure_log(), LUIGI, "job", result)
    assert _records() == []


def test_a_failing_record_is_reported(store):
    class Broken:
        def add(self, record):
            raise RuntimeError("firestore down")

    result = erasure.erase_jobs(store, ["j1"], LUIGI)
    assert erasure.record_erasure(Broken(), LUIGI, "job", result) is False
    assert "registro" in erasure.result_message(result, record_ok=False)


def test_application_log_line_has_ids_and_counts_only(store, caplog):
    caplog.set_level("INFO", logger="gateway.erasure")
    result = erasure.erase_chat(store, FRIEND, LUIGI)
    erasure.record_erasure(erasure.make_erasure_log(), LUIGI, "chat", result)
    lines = [r.getMessage() for r in caplog.records if "[erasure]" in r.getMessage()]
    assert len(lines) == 1 and "deleted=2" in lines[0] and "j1,j2" in lines[0]
    assert str(FRIEND) not in lines[0] and "IBAN" not in lines[0]


# ── /cancella: the card ──────────────────────────────────────────────────────


def test_command_shows_a_card_and_deletes_nothing(store):
    bot = FakeBot()
    assert _run(at.handle_admin_message(bot, store, _msg("/cancella j1"))) is True
    assert _ids(store) == ["g1", "j1", "j2", "other"]
    (chat, text, kw), = bot.sent
    assert "j1" in text and "delivered" in text and "2026-10-09" in text
    assert "IBAN" not in text and "malattia" not in text and str(FRIEND) not in text
    assert kw["reply_markup"] is not None


def test_chat_command_card_counts_statuses_and_dates_without_text(store):
    bot = FakeBot()
    _run(at.handle_admin_message(bot, store, _msg(f"/cancella chat {FRIEND}")))
    text = bot.texts()[0]
    assert "2 job" in text and "delivered" in text and "rejected" in text and "2026-10-10" in text
    assert "IBAN" not in text and "malattia" not in text and "landing" not in text
    assert _ids(store) == ["g1", "j1", "j2", "other"]


def test_card_warns_about_busy_jobs(store):
    store.put(_job("busy", status="running"))
    card = erasure.confirmation_card([store.get("busy"), store.get("j1")], "chat")
    assert "NON verranno cancellati" in card and "/sweep" in card


def test_card_is_capped_for_big_chats():
    jobs = [_job(f"x{i}") for i in range(40)]
    card = erasure.confirmation_card(jobs, "chat")
    assert "40 job" in card and "e altri 25" in card


def test_buttons_fit_telegram_limit_also_for_negative_chat_ids(store):
    for action, target in (("erase_job", "j1"), ("erase_chat", GROUP), ("erase_chat", "-" + "9" * 20),
                           ("erase_cancel", "x")):
        for row in admin.erase_keyboard(action, target):
            for button in row:
                assert len(button["callback_data"].encode()) <= 64
                assert admin.decode_callback(button["callback_data"]) is not None
    assert admin.decode_callback(admin.encode_callback("erase_chat", GROUP)) == ("erase_chat", GROUP)


@pytest.mark.parametrize("text", ["/cancella", "/cancella a b c", "/cancella chat", "/cancella chat abc",
                                  "/cancella chat 12 34", "/cancella ../x", "/cancella " + "a" * 62])
def test_bad_arguments_show_usage(store, text):
    bot = FakeBot()
    _run(at.handle_admin_message(bot, store, _msg(text)))
    assert "Uso:" in bot.texts()[0] and "/cancella" in bot.texts()[0]
    assert len(store.all_jobs()) == 4


def test_unknown_job_and_chat_without_jobs(store):
    bot = FakeBot()
    _run(at.handle_admin_message(bot, store, _msg("/cancella ghost")))
    _run(at.handle_admin_message(bot, store, _msg("/cancella chat 1")))
    assert "non trovato" in bot.texts()[0]
    assert "Nessun job" in bot.texts()[1]
    assert all(kw.get("reply_markup") is None for _, _, kw in bot.sent)


def test_stranger_command_is_swallowed(store):
    bot = FakeBot()
    assert _run(at.handle_admin_message(bot, store, _msg("/cancella j1", from_id=STRANGER))) is True
    assert bot.texts() == ["Comando non disponibile."]
    assert len(store.all_jobs()) == 4


def test_refuse_admin_command_also_covers_cancella():
    bot = FakeBot()
    assert _run(at.refuse_admin_command(bot, _msg("/cancella j1"))) is True
    assert bot.texts() == ["Comando non disponibile."]


# ── /cancella: Conferma and Annulla ──────────────────────────────────────────


def test_conferma_deletes_records_and_gives_the_checklist(store):
    bot = FakeBot()
    _run(at.handle_callback(bot, store, _cb(admin.encode_callback("erase_chat", str(FRIEND)))))
    assert _ids(store) == ["g1", "other"]
    (rec,) = _records()
    assert rec["count"] == 2 and rec["scope"] == "chat"
    report = bot.texts()[-1]
    assert "Cancellati 2 job" in report
    assert "E-mail" in report and "Telegram" in report and "30 giorni" in report
    assert "IBAN" not in report and str(FRIEND) not in report
    assert bot.edited and "Cancellazione eseguita" in bot.edited[0][2]


def test_conferma_for_a_single_job(store):
    bot = FakeBot()
    _run(at.handle_callback(bot, store, _cb(admin.encode_callback("erase_job", "j1"))))
    assert _ids(store) == ["g1", "j2", "other"]
    assert _records()[0]["scope"] == "job"


def test_negative_chat_id_roundtrip(store):
    _run(at.handle_callback(FakeBot(), store, _cb(admin.encode_callback("erase_chat", GROUP))))
    assert _ids(store) == ["j1", "j2", "other"]


def test_annulla_leaves_everything(store):
    bot = FakeBot()
    _run(at.handle_callback(bot, store, _cb(admin.encode_callback("erase_cancel", "x"))))
    assert len(store.all_jobs()) == 4 and _records() == []
    assert "Annullato" in bot.edited[0][2]


def test_double_conferma_is_harmless_and_says_so(store):
    bot = FakeBot()
    data = admin.encode_callback("erase_job", "j1")
    _run(at.handle_callback(bot, store, _cb(data)))
    _run(at.handle_callback(bot, store, _cb(data)))
    assert len(_records()) == 1
    assert "gia' cancellato" in bot.answered[-1][1] or "gia' fatto" in bot.answered[-1][1]
    assert "Niente da cancellare" in bot.texts()[-1]
    assert "Da fare a mano" not in bot.texts()[-1]


def test_conferma_after_jobs_are_gone(store):
    for j in ("j1", "j2"):
        store.delete(j)
    bot = FakeBot()
    _run(at.handle_callback(bot, store, _cb(admin.encode_callback("erase_chat", str(FRIEND)))))
    assert "Niente da cancellare" in bot.texts()[-1] and _records() == []


def test_conferma_refuses_a_job_that_became_busy_since_the_card(store):
    store.put(_job("busy", status="awaiting_review"))
    store.transition("busy", "awaiting_review", {"status": "delivering"})
    bot = FakeBot()
    _run(at.handle_callback(bot, store, _cb(admin.encode_callback("erase_job", "busy"))))
    assert store.get("busy") is not None and _records() == []
    assert "/sweep" in bot.texts()[-1] and bot.answered[-1][2] is True


def test_a_stranger_cannot_confirm_or_cancel(store):
    bot = FakeBot()
    for data in (admin.encode_callback("erase_chat", str(FRIEND)), admin.encode_callback("erase_job", "j1"),
                 admin.encode_callback("erase_cancel", "x")):
        _run(at.handle_callback(bot, store, _cb(data, from_id=STRANGER)))
    assert len(store.all_jobs()) == 4 and _records() == [] and bot.edited == []
    assert all(a[1] == "Non autorizzato." for a in bot.answered)


def test_forged_callback_with_a_malformed_target_does_nothing(store):
    bot = FakeBot()
    _run(at.handle_callback(bot, store, _cb("ec:abc")))
    assert len(store.all_jobs()) == 4 and _records() == []
    assert bot.answered[-1][1] == "Azione non valida."
