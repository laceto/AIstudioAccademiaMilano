"""Tests for gateway/admin_telegram.py and its wiring in the /webhook/telegram route.

Luigi presses a button (or types a command) in Telegram; the job is decided once,
Luigi sees the outcome, and the person who asked is told. Nobody else can decide.
"""

import asyncio

import pytest

from gateway import admin_telegram as at
from gateway.jobstore import FileJobStore

LUIGI = 5670736210
FRIEND = 190776580
SECRET = "s3cret-Token_for-tests"
HEADER = "X-Telegram-Bot-Api-Secret-Token"


class FakeBot:
    def __init__(self, token=None, fail_for=()):
        self.sent, self.answered, self.edited = [], [], []
        self.fail_for = set(fail_for)

    async def send_message(self, chat_id, text, **kw):
        if chat_id in self.fail_for:
            raise RuntimeError("Forbidden: bot was blocked by the user")
        self.sent.append((chat_id, text, kw))

    async def answer_callback_query(self, callback_query_id, text=None, show_alert=False, **kw):
        self.answered.append((callback_query_id, text, show_alert))

    async def edit_message_text(self, chat_id, message_id, text, **kw):
        self.edited.append((chat_id, message_id, text, kw))

    def to(self, chat_id):
        return [t for c, t, _ in self.sent if c == chat_id]


@pytest.fixture(autouse=True)
def _env(monkeypatch):
    monkeypatch.delenv("ADMIN_TELEGRAM_IDS", raising=False)
    monkeypatch.setenv("NOTIFY_TELEGRAM_CHAT_IDS", str(LUIGI))


def _job(job_id="abc123", product="static_landing_page", status="needs_review", created="2026-10-09T10:00:00+00:00"):
    return {
        "job_id": job_id, "status": status, "channel": "telegram", "text": "voglio un sito",
        "metadata": {"chat_id": str(FRIEND)}, "created_at": created,
        "classification": {"product_type": product, "confidence": 0.5, "summary": "un sito"},
    }


@pytest.fixture
def store(tmp_path):
    s = FileJobStore(str(tmp_path))
    s.put(_job())
    return s


def _cb(data, from_id=LUIGI, text="Richiesta da rivedere\n\nJob ID: abc123"):
    return {
        "id": "cb1", "from": {"id": from_id}, "data": data,
        "message": {"message_id": 77, "chat": {"id": LUIGI}, "text": text},
    }


def _run(coro):
    return asyncio.run(coro)


# ── buttons ──────────────────────────────────────────────────────────────────


def test_approve_button_decides_edits_the_card_and_tells_the_user(store):
    bot = FakeBot()
    _run(at.handle_callback(bot, store, _cb("ap:abc123")))
    job = store.get("abc123")
    assert job["status"] == "approved" and job["price"] == 9.9  # catalogue price of static_landing_page
    assert bot.answered[0][0] == "cb1" and "9.90" in bot.answered[0][1]
    chat_id, message_id, text, kw = bot.edited[0]
    assert (chat_id, message_id) == (LUIGI, 77) and "Approvata" in text
    assert not kw.get("reply_markup")  # buttons removed
    assert "approvata" in bot.to(FRIEND)[0].lower() and "9.90" in bot.to(FRIEND)[0]


def test_free_button_approves_at_zero(store):
    bot = FakeBot()
    _run(at.handle_callback(bot, store, _cb("fr:abc123")))
    assert store.get("abc123")["price"] == 0.0
    assert "gratuit" in bot.to(FRIEND)[0].lower()


def test_reject_button(store):
    bot = FakeBot()
    _run(at.handle_callback(bot, store, _cb("rj:abc123")))
    assert store.get("abc123")["status"] == "rejected"
    assert "non possiamo" in bot.to(FRIEND)[0].lower()


def test_a_stranger_pressing_a_button_changes_nothing(store):
    bot = FakeBot()
    _run(at.handle_callback(bot, store, _cb("ap:abc123", from_id=FRIEND)))
    assert store.get("abc123")["status"] == "needs_review"
    assert bot.answered[0][2] is True  # alert shown
    assert not bot.sent and not bot.edited


def test_second_press_is_told_it_was_already_decided(store):
    bot = FakeBot()
    _run(at.handle_callback(bot, store, _cb("ap:abc123")))
    _run(at.handle_callback(bot, store, _cb("rj:abc123")))
    assert store.get("abc123")["status"] == "approved"
    assert "già" in bot.answered[1][1].lower()
    assert len(bot.to(FRIEND)) == 1  # the user is told once


def test_garbage_callback_data_is_ignored(store):
    bot = FakeBot()
    _run(at.handle_callback(bot, store, _cb("zz:abc123")))
    assert store.get("abc123")["status"] == "needs_review" and bot.answered


def test_forged_approve_without_a_catalogue_price_is_refused(tmp_path):
    s = FileJobStore(str(tmp_path))
    s.put(_job(product="unknown_product"))
    bot = FakeBot()
    _run(at.handle_callback(bot, s, _cb("ap:abc123")))
    assert s.get("abc123")["status"] == "needs_review"
    assert "prezzo" in bot.answered[0][1].lower()


def test_unknown_job(store):
    bot = FakeBot()
    _run(at.handle_callback(bot, store, _cb("ap:ghost")))
    assert "non trovata" in bot.answered[0][1].lower()


def test_user_unreachable_is_reported_to_luigi_but_the_decision_stands(store):
    bot = FakeBot(fail_for={FRIEND})
    _run(at.handle_callback(bot, store, _cb("ap:abc123")))
    assert store.get("abc123")["status"] == "approved"
    assert any("non sono riuscito" in t.lower() for t in bot.to(LUIGI))


def test_non_telegram_jobs_are_decided_without_messaging_anyone(tmp_path):
    s = FileJobStore(str(tmp_path))
    job = _job()
    job["channel"] = "api"
    job["metadata"] = {"chat_id": ""}
    s.put(job)
    bot = FakeBot()
    _run(at.handle_callback(bot, s, _cb("ap:abc123")))
    # nobody to tell on a non-Telegram channel; Luigi still hears about the pipeline
    assert s.get("abc123")["status"] == "approved" and not bot.to(FRIEND)


# ── set a price: button, force-reply, answer ─────────────────────────────────


def _msg(text, from_id=LUIGI, reply_to=None):
    m = {"message_id": 5, "from": {"id": from_id}, "chat": {"id": from_id}, "text": text}
    if reply_to:
        m["reply_to_message"] = {"message_id": 4, "text": reply_to}
    return m


def test_set_price_button_asks_for_the_price(store):
    bot = FakeBot()
    _run(at.handle_callback(bot, store, _cb("pr:abc123")))
    prompt = bot.to(LUIGI)[0]
    assert "Job ID: abc123" in prompt
    assert bot.sent[0][2].get("reply_markup") is not None  # force-reply
    assert store.get("abc123")["status"] == "needs_review"


def test_replying_with_a_price_approves(store):
    bot = FakeBot()
    handled = _run(at.handle_admin_message(bot, store, _msg("12,50", reply_to=at.PRICE_PROMPT.format(job_id="abc123"))))
    assert handled and store.get("abc123")["price"] == 12.5
    assert "12.50" in bot.to(FRIEND)[0]


def test_replying_with_junk_keeps_the_job_pending(store):
    bot = FakeBot()
    handled = _run(at.handle_admin_message(bot, store, _msg("boh", reply_to=at.PRICE_PROMPT.format(job_id="abc123"))))
    assert handled and store.get("abc123")["status"] == "needs_review"
    assert "prezzo non valido" in bot.to(LUIGI)[0].lower()


def test_a_stranger_replying_to_a_price_prompt_is_not_handled(store):
    bot = FakeBot()
    handled = _run(at.handle_admin_message(bot, store, _msg("1", from_id=FRIEND, reply_to=at.PRICE_PROMPT.format(job_id="abc123"))))
    assert handled is False and store.get("abc123")["status"] == "needs_review"


def test_ordinary_messages_are_left_to_the_normal_flow(store):
    assert _run(at.handle_admin_message(FakeBot(), store, _msg("ciao, voglio un sito"))) is False
    assert _run(at.handle_admin_message(FakeBot(), store, _msg("12,50"))) is False  # not a reply to a prompt


# ── commands ─────────────────────────────────────────────────────────────────


def test_pending_lists_jobs_with_buttons(store):
    bot = FakeBot()
    assert _run(at.handle_admin_message(bot, store, _msg("/pending")))
    assert any("abc123" in t for t in bot.to(LUIGI))
    assert any(kw.get("reply_markup") for _, _, kw in bot.sent)


def test_pending_when_nothing_waits(tmp_path):
    bot = FakeBot()
    _run(at.handle_admin_message(bot, FileJobStore(str(tmp_path)), _msg("/pending")))
    assert "nessuna" in bot.to(LUIGI)[0].lower()


def test_approve_command_with_a_price(store):
    bot = FakeBot()
    _run(at.handle_admin_message(bot, store, _msg("/approve abc123 14,90")))
    assert store.get("abc123")["price"] == 14.9


def test_approve_command_without_a_price_uses_the_catalogue(store):
    _run(at.handle_admin_message(FakeBot(), store, _msg("/approve abc123")))
    assert store.get("abc123")["price"] == 9.9


def test_approve_command_gratis(store):
    _run(at.handle_admin_message(FakeBot(), store, _msg("/approve abc123 gratis")))
    assert store.get("abc123")["price"] == 0.0


def test_approve_command_without_a_price_for_an_unknown_product(tmp_path):
    s = FileJobStore(str(tmp_path))
    s.put(_job(product="unknown_product"))
    bot = FakeBot()
    _run(at.handle_admin_message(bot, s, _msg("/approve abc123")))
    assert s.get("abc123")["status"] == "needs_review" and "prezzo" in bot.to(LUIGI)[0].lower()


def test_reject_command_keeps_the_reason_internal(store):
    bot = FakeBot()
    _run(at.handle_admin_message(bot, store, _msg("/reject abc123 sospetta frode")))
    job = store.get("abc123")
    assert job["status"] == "rejected" and job["decision"]["reason"] == "sospetta frode"
    assert "frode" not in bot.to(FRIEND)[0]


def test_command_usage_help(store):
    bot = FakeBot()
    _run(at.handle_admin_message(bot, store, _msg("/approve")))
    assert "uso" in bot.to(LUIGI)[0].lower()


def test_command_with_the_bot_name_suffix(store):
    _run(at.handle_admin_message(FakeBot(), store, _msg("/approve@AIStudioMilanoBot abc123 5")))
    assert store.get("abc123")["price"] == 5.0


def test_a_stranger_typing_a_command_is_refused_and_not_queued(store):
    bot = FakeBot()
    handled = _run(at.handle_admin_message(bot, store, _msg("/approve abc123 0", from_id=FRIEND)))
    assert handled is True  # swallowed: it must not become a job request
    assert store.get("abc123")["status"] == "needs_review"
    assert "non disponibile" in bot.to(FRIEND)[0].lower()


# ── wired into the webhook ───────────────────────────────────────────────────


@pytest.fixture
def client(monkeypatch, tmp_path):
    import telegram
    from fastapi.testclient import TestClient

    import gateway.bot_telegram  # noqa: F401  load telegram.ext against the real Bot before patching
    from gateway import api

    bot = FakeBot()

    class _SharedBot(FakeBot):  # a class, not a function: telegram.ext subclasses Bot
        def __new__(cls, token=None):
            return bot

        def __init__(self, token=None):
            pass

    monkeypatch.setattr(telegram, "Bot", _SharedBot)
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "123:fake")
    monkeypatch.setenv("TELEGRAM_WEBHOOK_SECRET", SECRET)
    monkeypatch.delenv("GATEWAY_SYNC_REPLY", raising=False)
    monkeypatch.setattr(api, "_adapter", api.PipelineAdapter(queue_dir=str(tmp_path)))
    api._adapter.store.put(_job())
    return TestClient(api.app, headers={HEADER: SECRET}), bot, api._adapter.store


def test_webhook_routes_a_button_press(client):
    c, bot, store = client
    resp = c.post("/webhook/telegram", json={"update_id": 1, "callback_query": _cb("ap:abc123")})
    assert resp.status_code == 200 and store.get("abc123")["status"] == "approved"


def test_webhook_routes_a_command_and_does_not_create_a_job(client):
    c, bot, store = client
    before = len(store.list_by_status("queued"))
    c.post("/webhook/telegram", json={"message": _msg("/pending")})
    assert len(store.list_by_status("queued")) == before


def test_webhook_swallows_a_strangers_command(client):
    c, bot, store = client
    c.post("/webhook/telegram", json={"message": _msg("/approve abc123 1", from_id=FRIEND)})
    assert store.get("abc123")["status"] == "needs_review"
    assert not store.list_by_status("queued")


def test_webhook_still_handles_ordinary_requests(client):
    c, bot, store = client
    c.post("/webhook/telegram", json={"message": _msg("voglio un sito", from_id=FRIEND)})
    assert any("Ricevuto" in t for t in bot.to(FRIEND))


# ── the webhook must prove the update comes from Telegram ────────────────────
# Luigi is recognised by the numeric id inside the payload, which anyone can forge
# unless Telegram's secret token is checked.


def test_webhook_rejects_requests_without_the_secret(client):
    c, bot, store = client
    forged = {"callback_query": _cb("ap:abc123")}
    assert c.post("/webhook/telegram", json=forged, headers={HEADER: ""}).status_code == 403
    assert c.post("/webhook/telegram", json=forged, headers={HEADER: "wrong"}).status_code == 403
    assert store.get("abc123")["status"] == "needs_review"
    assert not bot.sent and not bot.answered


def test_webhook_rejects_ordinary_messages_without_the_secret_too(client):
    c, bot, store = client
    r = c.post("/webhook/telegram", json={"message": _msg("ciao", from_id=FRIEND)}, headers={HEADER: "wrong"})
    assert r.status_code == 403 and not store.list_by_status("queued")


def test_without_a_configured_secret_admin_actions_stay_off(client, monkeypatch):
    c, bot, store = client
    monkeypatch.delenv("TELEGRAM_WEBHOOK_SECRET")
    # a forged button press from "Luigi" does nothing
    c.post("/webhook/telegram", json={"callback_query": _cb("ap:abc123")}, headers={})
    assert store.get("abc123")["status"] == "needs_review"
    # a forged command is refused and not queued as a request
    c.post("/webhook/telegram", json={"message": _msg("/approve abc123 0")}, headers={})
    assert store.get("abc123")["status"] == "needs_review"
    assert any("non disponibile" in t.lower() for t in bot.to(LUIGI))
    assert not store.list_by_status("queued")
    # ordinary users are still served
    c.post("/webhook/telegram", json={"message": _msg("voglio un sito", from_id=FRIEND)}, headers={})
    assert any("Ricevuto" in t for t in bot.to(FRIEND))


def test_refuse_admin_command_only_swallows_commands(store):
    bot = FakeBot()
    assert _run(at.refuse_admin_command(bot, _msg("/pending"))) is True
    assert _run(at.refuse_admin_command(bot, _msg("12,50"))) is False
    assert _run(at.refuse_admin_command(bot, _msg("ciao"))) is False
