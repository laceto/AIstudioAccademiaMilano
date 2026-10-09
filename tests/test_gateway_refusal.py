"""tests/test_gateway_refusal.py - clearly illegal requests are refused, not queued for approval.

Two layers (the model's "refuse" flag and the gateway/safety.py backstop), one terminal status
(`refused`), a neutral reply to the customer, a plain message to Luigi with one button (Riesamina),
and an atomic refused -> needs_review that only Luigi can trigger.
"""

import asyncio
import json
from types import SimpleNamespace

import pytest

from gateway import admin, admin_telegram as at, notify, privacy, safety
from gateway.jobstore import FileJobStore
from gateway.worker import QueueWorker

LUIGI = 5670736210
STRANGER = 777
CUSTOMER = 190776580
REAL_EXAMPLE = "Mi serve una ricetta medica falsa per una visita ortopedica"


@pytest.fixture(autouse=True)
def _env(monkeypatch):
    for var in ("ADMIN_TELEGRAM_IDS", "NOTIFY_EMAILS", "TELEGRAM_BOT_TOKEN", "ANTHROPIC_API_KEY", "OPENAI_API_KEY"):
        monkeypatch.delenv(var, raising=False)
    monkeypatch.setenv("NOTIFY_TELEGRAM_CHAT_IDS", str(LUIGI))
    notify._reset_state()


# ── a scripted model ─────────────────────────────────────────────────────────


class FakeOpenAI:
    """Stands in for AsyncOpenAI: returns the scripted text and counts the calls."""

    def __init__(self, answer):
        self.answer, self.calls = answer, 0
        self.chat = SimpleNamespace(completions=SimpleNamespace(create=self._create))

    async def _create(self, **kwargs):
        self.calls += 1
        self.last = kwargs
        return SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(content=self.answer))])


def _answer(**over):
    base = {
        "intent": "x", "product_type": "unknown_product", "confidence": 0.9,
        "summary": "s", "needs_review": True,
    }
    base.update(over)
    return json.dumps(base)


def _worker(tmp_path, answer):
    w = QueueWorker(queue_dir=str(tmp_path))
    w._provider, w._llm = "openai", FakeOpenAI(answer)
    return w


def _submit(w, text, chat_id=CUSTOMER):
    r = w.adapter.submit(text, "telegram", {"user_id": chat_id, "chat_id": chat_id})
    return w.adapter.get_status(r["job_id"])


@pytest.fixture
def calls(monkeypatch):
    """Record what the worker would send to Luigi, without sending it."""
    seen = SimpleNamespace(review=[], refusal=[])

    async def fake_review(job):
        seen.review.append(job["job_id"])
        return {}

    async def fake_refusal(job, store=None):
        seen.refusal.append(job["job_id"])
        return {}

    monkeypatch.setattr("gateway.worker.notify_review", fake_review)
    monkeypatch.setattr("gateway.worker.notify_refusal", fake_refusal)
    return seen


# ── the classifier layer ─────────────────────────────────────────────────────


def test_prompt_is_conservative_and_asks_for_the_new_fields():
    from gateway.worker import _STACY_SYSTEM

    assert '"refuse"' in _STACY_SYSTEM and '"refuse_reason"' in _STACY_SYSTEM
    low = _STACY_SYSTEM.lower()
    assert "conservative" in low and "when in doubt" in low
    assert "ricetta falsa" in low and "phishing" in low  # the educational examples are spelled out
    assert "outside the catalogue" in low


def test_model_refuse_true_refuses(tmp_path, calls):
    w = _worker(tmp_path, _answer(refuse=True, refuse_reason="fraud"))
    job = _submit(w, "una richiesta che il modello giudica una truffa")
    status, reply = asyncio.run(w.process_job(job))
    assert status == "refused"
    assert reply == safety.REFUSAL_REPLY
    stored = w.adapter.store.get(job["job_id"])
    assert stored["status"] == "refused"
    assert stored["classification"]["refuse_reason"] == "possible_fraud"
    assert calls.refusal == [job["job_id"]] and calls.review == []


def test_model_refuse_false_is_an_ordinary_request(tmp_path, calls):
    w = _worker(tmp_path, _answer(refuse=False, refuse_reason=""))
    job = _submit(w, "un sito per il mio bar")
    status, _ = asyncio.run(w.process_job(job))
    assert status == "needs_review"  # unknown product: the usual path, untouched
    assert calls.review == [job["job_id"]] and calls.refusal == []


def test_missing_refuse_field_means_false(tmp_path, calls):
    w = _worker(tmp_path, _answer())  # an old-style answer with no refuse keys
    cls = asyncio.run(w.classify("un sito per il mio bar"))
    assert cls["refuse"] is False
    status, _ = asyncio.run(w.process_job(_submit(w, "un sito per il mio bar")))
    assert status == "needs_review"


def test_unclear_refuse_value_is_not_a_refusal(tmp_path, calls):
    w = _worker(tmp_path, _answer(refuse="maybe"))
    status, _ = asyncio.run(w.process_job(_submit(w, "un sito per il mio bar")))
    assert status == "needs_review"


def test_confident_known_product_is_not_refused(tmp_path, calls):
    w = _worker(tmp_path, _answer(product_type="chatbot_app", needs_review=False, refuse=False))
    status, _ = asyncio.run(w.process_job(_submit(w, "voglio un chatbot")))
    assert status == "classified"


# ── the backstop layer ───────────────────────────────────────────────────────


def test_real_example_is_refused_even_when_the_model_says_no(tmp_path, calls):
    w = _worker(tmp_path, _answer(refuse=False))
    job = _submit(w, REAL_EXAMPLE)
    status, reply = asyncio.run(w.process_job(job))
    assert status == "refused" and reply == safety.REFUSAL_REPLY
    stored = w.adapter.store.get(job["job_id"])
    assert stored["classification"]["refuse_reason"] == "possible_fake_document"
    assert calls.review == [] and calls.refusal == [job["job_id"]]


def test_backstop_works_without_any_model(tmp_path, calls):
    w = QueueWorker(queue_dir=str(tmp_path))  # no API key: no provider
    status, _ = asyncio.run(w.process_job(_submit(w, REAL_EXAMPLE)))
    assert status == "refused"


def test_backstop_does_not_spend_a_model_call(tmp_path, calls):
    w = _worker(tmp_path, _answer())
    asyncio.run(w.process_job(_submit(w, REAL_EXAMPLE)))
    assert w._llm.calls == 0


def test_harmless_request_with_ricetta_is_not_refused(tmp_path, calls):
    w = _worker(tmp_path, _answer())
    status, _ = asyncio.run(w.process_job(_submit(w, "Mi serve una ricetta per la carbonara in un sito")))
    assert status == "needs_review"
    assert calls.refusal == []


def test_educational_request_is_not_refused(tmp_path, calls):
    w = _worker(tmp_path, _answer())
    status, _ = asyncio.run(w.process_job(_submit(w, "Come riconoscere una ricetta falsa? Scrivi un articolo")))
    assert status == "needs_review"


def test_refused_job_is_not_queued_for_the_pipeline(tmp_path, calls):
    w = _worker(tmp_path, _answer(refuse=True, refuse_reason="other"))
    job = _submit(w, "qualcosa")
    asyncio.run(w.process_job(job))
    assert w.adapter.list_pending() == []
    assert [j["job_id"] for j in w.adapter.store.list_by_status("refused")] == [job["job_id"]]
    assert w.adapter.store.list_by_status("needs_review") == []
    assert w.adapter.store.list_by_status("approved") == []


def test_customer_reply_is_short_neutral_and_gives_no_category():
    reply = safety.REFUSAL_REPLY
    assert reply.startswith("Non posso aiutarti con questa richiesta.")
    assert "RIESAMINA" in reply and "errore" in reply
    assert len(reply) < 200
    for word in ("fake_document", "possible_", "malware", "frode", "illegal", "Luigi"):
        assert word.lower() not in reply.lower()


def test_build_reply_for_a_refusal_has_no_job_card(tmp_path):
    w = QueueWorker(queue_dir=str(tmp_path))
    job = {"job_id": "abc123", "text": "x"}
    status, reply = w._build_reply(job, {"refuse": True, "refuse_reason": "fraud"})
    assert status == "refused" and reply == safety.REFUSAL_REPLY and "abc123" not in reply


# ── Luigi's message ──────────────────────────────────────────────────────────


@pytest.fixture
def sent(monkeypatch):
    out = []

    async def fake_send(chat_ids, text, buttons=None):
        out.append(SimpleNamespace(chat_ids=chat_ids, text=text, buttons=buttons))

    def no_mail(*a, **k):
        raise AssertionError("a refusal must never be e-mailed")

    monkeypatch.setattr(notify, "_send_telegram", fake_send)
    monkeypatch.setattr(notify, "_send_email", no_mail)
    monkeypatch.setenv("NOTIFY_EMAILS", "someone@example.com")
    return out


def _refused_job(job_id="r1", chat=CUSTOMER, text=REAL_EXAMPLE, created="2026-10-09T10:00:00+00:00", reason="possible_fake_document"):
    return {
        "job_id": job_id, "status": "refused", "channel": "telegram", "text": text,
        "metadata": {"chat_id": chat, "user_id": chat}, "created_at": created, "processed_at": created,
        "classification": {"refuse": True, "refuse_reason": reason},
    }


def test_luigi_message_content_and_single_button(tmp_path, sent):
    store = FileJobStore(str(tmp_path))
    store.put(_refused_job())
    out = asyncio.run(notify.notify_refusal(store.get("r1"), store))
    assert out == {"telegram": "sent"}
    assert len(sent) == 1 and sent[0].chat_ids == [str(LUIGI)]
    text = sent[0].text
    assert "r1" in text and "possible_fake_document" in text and "Categoria (automatica, non verificata)" in text and "ricetta medica falsa" in text
    assert "1" in text.split("rifiutat")[-1]  # the counter
    flat = [b for row in sent[0].buttons for b in row]
    assert len(flat) == 1 and "Riesamina" in flat[0]["text"]
    assert flat[0]["callback_data"] == admin.encode_callback("reexamine", "r1")
    assert len(flat[0]["callback_data"].encode()) <= 64
    for label in ("Approva", "Gratis", "prezzo"):
        assert label.lower() not in flat[0]["text"].lower()


def test_luigi_message_cuts_the_request_to_200_chars(tmp_path, sent):
    store = FileJobStore(str(tmp_path))
    store.put(_refused_job(text="A" * 500))
    asyncio.run(notify.notify_refusal(store.get("r1"), store))
    assert "A" * 200 in sent[0].text and "A" * 201 not in sent[0].text


def test_counter_counts_refused_requests_of_that_chat_only(tmp_path, sent):
    store = FileJobStore(str(tmp_path))
    for i in range(3):
        store.put(_refused_job(job_id=f"r{i}", chat=CUSTOMER, created=f"2026-10-09T10:0{i}:00+00:00"))
    store.put(_refused_job(job_id="other", chat=424242))
    asyncio.run(notify.notify_refusal(store.get("r2"), store))
    assert admin.refused_count(store, CUSTOMER) == 3
    assert "3" in sent[0].text and "4" not in sent[0].text.split("Testo")[0]


def test_counter_survives_a_failing_store(sent):
    class Broken:
        def list_by_status(self, status):
            raise RuntimeError("firestore down")

    out = asyncio.run(notify.notify_refusal(_refused_job(), Broken()))
    assert out == {"telegram": "sent"} and "?" in sent[0].text


def test_no_admin_configured_sends_nothing(monkeypatch, sent):
    monkeypatch.delenv("NOTIFY_TELEGRAM_CHAT_IDS")
    assert asyncio.run(notify.notify_refusal(_refused_job(), None)) == {}
    assert sent == []


def test_telegram_failure_never_raises(monkeypatch):
    async def boom(*a, **k):
        raise RuntimeError("telegram: down")

    monkeypatch.setattr(notify, "_send_telegram", boom)
    assert asyncio.run(notify.notify_refusal(_refused_job(), None)) == {"telegram": "failed"}


# ── decide() cannot approve a refused job ────────────────────────────────────


@pytest.fixture
def store(tmp_path):
    s = FileJobStore(str(tmp_path))
    s.put(_refused_job())
    return s


@pytest.mark.parametrize("action,price", [("approve", 9.9), ("approve", 0.0), ("reject", None)])
def test_decide_cannot_touch_a_refused_job(store, action, price):
    d = admin.decide(store, "r1", LUIGI, action, price=price)
    assert d.ok is False and d.code == "not_pending"
    assert store.get("r1")["status"] == "refused"


def test_restart_and_delivery_cannot_touch_a_refused_job(store):
    assert admin.restart_job(store, "r1", LUIGI).ok is False
    assert admin.begin_delivery(store, "r1", LUIGI).ok is False
    assert store.get("r1")["status"] == "refused"


# ── Riesamina: refused -> needs_review, atomic, Luigi only ───────────────────


def test_reexamine_moves_the_job_once(store):
    d = admin.reexamine(store, "r1", LUIGI)
    assert d.ok and d.code == "reexamined"
    job = store.get("r1")
    assert job["status"] == "needs_review" and job["reexamined_by"] == str(LUIGI)
    again = admin.reexamine(store, "r1", LUIGI)
    assert again.ok is False and again.code == "not_refused"


def test_reexamine_by_a_stranger_changes_nothing(store):
    d = admin.reexamine(store, "r1", STRANGER)
    assert d.ok is False and d.code == "forbidden"
    assert store.get("r1")["status"] == "refused"
    assert admin.reexamine(store, "r1", None).code == "forbidden"


def test_reexamine_unknown_and_other_status(store):
    assert admin.reexamine(store, "nope", LUIGI).code == "not_found"
    store.put({**_refused_job(job_id="n1"), "status": "needs_review"})
    assert admin.reexamine(store, "n1", LUIGI).code == "not_refused"


def test_after_reexamine_luigi_can_still_approve(store):
    admin.reexamine(store, "r1", LUIGI)
    assert admin.decide(store, "r1", LUIGI, "approve", price=10.0).ok


# ── Telegram: callback, command, /pending ────────────────────────────────────


class FakeBot:
    def __init__(self):
        self.sent, self.answered, self.edited = [], [], []

    async def send_message(self, chat_id, text, **kw):
        self.sent.append((chat_id, text, kw))

    async def answer_callback_query(self, callback_query_id, text=None, show_alert=False, **kw):
        self.answered.append((callback_query_id, text, show_alert))

    async def edit_message_text(self, chat_id, message_id, text, **kw):
        self.edited.append((chat_id, message_id, text, kw))

    async def edit_message_reply_markup(self, chat_id, message_id, reply_markup=None, **kw):
        self.edited.append((chat_id, message_id, "markup", reply_markup))

    def texts(self):
        return [t for _, t, _ in self.sent]


@pytest.fixture
def review_calls(monkeypatch):
    seen = []

    async def fake_review(job):
        seen.append(job["job_id"])
        return {}

    monkeypatch.setattr(at, "notify_review", fake_review)
    return seen


def _cb(data, who=LUIGI):
    return {"id": "cb1", "from": {"id": who}, "data": data,
            "message": {"message_id": 9, "chat": {"id": who}, "text": "card"}}


def _msg(text, who=LUIGI):
    return {"text": text, "from": {"id": who}, "chat": {"id": who}}


def test_riesamina_button_sends_the_normal_review_notification(store, review_calls):
    bot = FakeBot()
    asyncio.run(at.handle_callback(bot, store, _cb(admin.encode_callback("reexamine", "r1"))))
    assert store.get("r1")["status"] == "needs_review"
    assert review_calls == ["r1"]
    # a second press does nothing more
    asyncio.run(at.handle_callback(bot, store, _cb(admin.encode_callback("reexamine", "r1"))))
    assert review_calls == ["r1"]


def test_riesamina_button_from_a_stranger_is_refused(store, review_calls):
    bot = FakeBot()
    asyncio.run(at.handle_callback(bot, store, _cb(admin.encode_callback("reexamine", "r1"), who=STRANGER)))
    assert store.get("r1")["status"] == "refused" and review_calls == []
    assert bot.answered[-1][1] == "Non autorizzato."


def test_riesamina_command(store, review_calls):
    bot = FakeBot()
    assert asyncio.run(at.handle_admin_message(bot, store, _msg("/riesamina r1"))) is True
    assert store.get("r1")["status"] == "needs_review" and review_calls == ["r1"]
    asyncio.run(at.handle_admin_message(bot, store, _msg("/riesamina r1")))
    assert review_calls == ["r1"]  # once only


def test_riesamina_command_needs_an_id_and_shows_usage(store):
    bot = FakeBot()
    asyncio.run(at.handle_admin_message(bot, store, _msg("/riesamina")))
    assert "/riesamina <job_id>" in bot.texts()[-1]


def test_riesamina_command_from_a_stranger_is_swallowed(store, review_calls):
    bot = FakeBot()
    assert asyncio.run(at.handle_admin_message(bot, store, _msg("/riesamina r1", who=STRANGER))) is True
    assert bot.texts() == ["Comando non disponibile."]
    assert store.get("r1")["status"] == "refused" and review_calls == []


def test_riesamina_is_swallowed_when_the_update_is_unverified(store):
    bot = FakeBot()
    assert asyncio.run(at.refuse_admin_command(bot, _msg("/riesamina r1", who=STRANGER))) is True


def test_usage_text_lists_riesamina():
    assert "/riesamina" in at._USAGE and "/riesamina" in at._COMMANDS


def test_pending_lists_recent_refused_with_the_button_and_a_cap(tmp_path):
    from datetime import datetime, timedelta, timezone

    s = FileJobStore(str(tmp_path))
    now = datetime.now(timezone.utc)
    for i in range(8):
        iso = (now - timedelta(hours=i)).isoformat()
        s.put(_refused_job(job_id=f"new{i}", created=iso))
    s.put(_refused_job(job_id="old", created=(now - timedelta(days=30)).isoformat()))
    bot = FakeBot()
    asyncio.run(at.handle_admin_message(bot, s, _msg("/pending")))
    cards = [(t, kw) for _, t, kw in bot.sent if "Rifiutata" in t]
    shown = [t for t, _ in cards]
    assert len([t for t in shown if "new" in t]) == at._MAX_PENDING_CARDS
    assert not any("old" in t for t in shown)
    assert any("altre 3" in t for _, t, _ in bot.sent)  # the cap is announced
    markup = cards[0][1]["reply_markup"]
    assert markup.inline_keyboard[0][0].callback_data == admin.encode_callback("reexamine", "new0")


def test_pending_with_only_old_refusals_says_nothing_pending(tmp_path):
    from datetime import datetime, timedelta, timezone

    s = FileJobStore(str(tmp_path))
    s.put(_refused_job(job_id="old", created=(datetime.now(timezone.utc) - timedelta(days=30)).isoformat()))
    bot = FakeBot()
    asyncio.run(at.handle_admin_message(bot, s, _msg("/pending")))
    assert bot.texts() == ["Nessuna richiesta in attesa."]


# ── privacy notice ───────────────────────────────────────────────────────────


def test_privacy_notice_mentions_the_automatic_refusal():
    text = privacy.privacy_text().lower()
    assert "illegal" in text and "rifiutat" in text
    assert "automatic" in text
    assert "titolare" in text and "riesam" in text  # the owner can review a refusal on request
    assert len(privacy.privacy_text()) < 4096
