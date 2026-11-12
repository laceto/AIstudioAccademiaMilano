"""Tests for the separate admin bot (TELEGRAM_ADMIN_BOT_TOKEN).

Luigi used to be customer and admin on one bot, so his test requests and his approval
cards shared a chat. With an admin token set, everything addressed to Luigi goes out
through the admin bot and the customer bot only talks to customers. Without it,
behaviour is the old single-bot one.
"""

import asyncio

import pytest

from gateway import notify

ADMIN_TOKEN = "999:admin"
CUSTOMER_TOKEN = "123:customer"


@pytest.fixture(autouse=True)
def _clean(monkeypatch):
    for var in ("TELEGRAM_BOT_TOKEN", "TELEGRAM_ADMIN_BOT_TOKEN", "NOTIFY_TELEGRAM_CHAT_IDS"):
        monkeypatch.delenv(var, raising=False)
    notify._reset_state()


def _fake_client(calls):
    class _Resp:
        status_code = 200

    class _Client:
        def __init__(self, **kw):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *a):
            return False

        async def post(self, url, json=None, data=None, files=None):
            calls.append(url)
            return _Resp()

    return _Client


# ── A1.1 admin_token ─────────────────────────────────────────────────────────


def test_admin_token_prefers_the_admin_bot(monkeypatch):
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", CUSTOMER_TOKEN)
    monkeypatch.setenv("TELEGRAM_ADMIN_BOT_TOKEN", ADMIN_TOKEN)
    assert notify.admin_token() == ADMIN_TOKEN


def test_admin_token_falls_back_to_the_customer_bot(monkeypatch):
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", CUSTOMER_TOKEN)
    assert notify.admin_token() == CUSTOMER_TOKEN


def test_admin_token_ignores_a_blank_admin_value(monkeypatch):
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", CUSTOMER_TOKEN)
    monkeypatch.setenv("TELEGRAM_ADMIN_BOT_TOKEN", "   ")
    assert notify.admin_token() == CUSTOMER_TOKEN


def test_admin_token_empty_when_nothing_is_set():
    assert notify.admin_token() == ""


# ── A1.2 the senders use it ──────────────────────────────────────────────────


def test_send_telegram_goes_out_through_the_admin_bot(monkeypatch):
    calls = []
    monkeypatch.setattr(notify.httpx, "AsyncClient", _fake_client(calls))
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", CUSTOMER_TOKEN)
    monkeypatch.setenv("TELEGRAM_ADMIN_BOT_TOKEN", ADMIN_TOKEN)
    asyncio.run(notify._send_telegram(["111"], "card"))
    assert calls == [f"https://api.telegram.org/bot{ADMIN_TOKEN}/sendMessage"]


def test_send_document_goes_out_through_the_admin_bot(monkeypatch):
    calls = []
    monkeypatch.setattr(notify.httpx, "AsyncClient", _fake_client(calls))
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", CUSTOMER_TOKEN)
    monkeypatch.setenv("TELEGRAM_ADMIN_BOT_TOKEN", ADMIN_TOKEN)
    asyncio.run(notify._send_document(["111"], "cap", "a.py", b"x", [[{"text": "ok", "callback_data": "a:b"}]]))
    assert calls == [f"https://api.telegram.org/bot{ADMIN_TOKEN}/sendDocument"]


def test_send_telegram_without_admin_bot_keeps_the_single_bot_behaviour(monkeypatch):
    calls = []
    monkeypatch.setattr(notify.httpx, "AsyncClient", _fake_client(calls))
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", CUSTOMER_TOKEN)
    asyncio.run(notify._send_telegram(["111"], "card"))
    assert calls == [f"https://api.telegram.org/bot{CUSTOMER_TOKEN}/sendMessage"]


def test_send_telegram_without_any_token_says_so():
    with pytest.raises(RuntimeError, match="not configured"):
        asyncio.run(notify._send_telegram(["111"], "card"))


# ── A2 admin bot vs customer bot inside admin_telegram ───────────────────────

from gateway import admin_telegram as at  # noqa: E402
from gateway.admin import encode_callback  # noqa: E402
from gateway.jobstore import FileJobStore  # noqa: E402

LUIGI = 5670736210
FRIEND = 190776580


class FakeBot:
    def __init__(self):
        self.sent, self.answered, self.edited, self.documents = [], [], [], []

    async def send_message(self, chat_id, text, **kw):
        self.sent.append((chat_id, text, kw))

    async def send_document(self, chat_id, document, filename=None, caption=None, **kw):
        self.documents.append((chat_id, filename, caption))

    async def answer_callback_query(self, callback_query_id, text=None, show_alert=False, **kw):
        self.answered.append((callback_query_id, text))

    async def edit_message_text(self, chat_id, message_id, text, **kw):
        self.edited.append((chat_id, message_id, text))

    async def edit_message_reply_markup(self, chat_id, message_id, reply_markup=None, **kw):
        self.edited.append((chat_id, message_id, reply_markup))

    def to(self, chat_id):
        return [t for c, t, _ in self.sent if c == chat_id]


def _job(status="needs_review"):
    return {
        "job_id": "abc123", "status": status, "channel": "telegram", "text": "voglio un sito",
        "metadata": {"chat_id": str(FRIEND)}, "created_at": "2026-10-09T10:00:00+00:00",
        "classification": {"product_type": "static_landing_page", "confidence": 0.5, "summary": "un sito"},
    }


def _cb(data):
    return {
        "id": "cb1", "from": {"id": LUIGI}, "data": data,
        "message": {"message_id": 77, "chat": {"id": LUIGI}, "text": "Job ID: abc123"},
    }


@pytest.fixture
def store(tmp_path, monkeypatch):
    monkeypatch.setenv("NOTIFY_TELEGRAM_CHAT_IDS", str(LUIGI))
    monkeypatch.delenv("ADMIN_TELEGRAM_IDS", raising=False)
    return FileJobStore(str(tmp_path))


def test_approving_edits_the_card_on_the_admin_bot_and_tells_the_customer_on_the_customer_bot(store):
    store.put(_job())
    admin, customer = FakeBot(), FakeBot()
    asyncio.run(at.handle_callback(at.AdminBot(admin, customer), store, _cb(encode_callback("approve", "abc123"))))
    assert admin.answered and admin.edited                     # Luigi's card is handled on the admin bot
    assert not admin.to(FRIEND)                                # the customer never hears from the admin bot
    assert "approvata" in customer.to(FRIEND)[0].lower()       # ...only from the customer bot
    assert not customer.answered and not customer.edited       # and the customer bot never touches Luigi's card


def test_sending_the_file_uses_the_customer_bot_and_confirms_on_the_admin_bot(store):
    job = _job("awaiting_review")
    job["result"] = {"ok": True, "content": "print(1)", "filename": "a.py"}
    store.put(job)
    admin, customer = FakeBot(), FakeBot()
    asyncio.run(at.handle_callback(at.AdminBot(admin, customer), store, _cb(encode_callback("send", "abc123"))))
    assert [d[0] for d in customer.documents] == [FRIEND] and not admin.documents
    assert any("inviato" in t.lower() for t in admin.to(LUIGI))
    assert store.get("abc123")["status"] == "delivered"


def test_a_plain_bot_still_does_everything_itself(store):
    """No admin bot configured: the single bot plays both roles, as before."""
    store.put(_job())
    bot = FakeBot()
    asyncio.run(at.handle_callback(bot, store, _cb(encode_callback("approve", "abc123"))))
    assert bot.answered and bot.to(FRIEND)


def test_adminbot_without_a_customer_bot_uses_the_admin_bot_for_both(store):
    store.put(_job())
    admin = FakeBot()
    asyncio.run(at.handle_callback(at.AdminBot(admin), store, _cb(encode_callback("approve", "abc123"))))
    assert admin.answered and admin.to(FRIEND)


# ── A3 webhook routes ────────────────────────────────────────────────────────

SECRET = "s3cret-Token_for-tests"
HEADER = "X-Telegram-Bot-Api-Secret-Token"


def _msg(text, from_id=LUIGI, reply_to=None):
    m = {"message_id": 5, "from": {"id": from_id}, "chat": {"id": from_id}, "text": text}
    if reply_to:
        m["reply_to_message"] = {"text": reply_to}
    return m


@pytest.fixture
def hook(monkeypatch, tmp_path):
    """Both bots configured. Returns (client, {token: FakeBot}, store)."""
    import telegram
    from fastapi.testclient import TestClient

    import gateway.bot_telegram  # noqa: F401  load telegram.ext against the real Bot before patching
    from gateway import api

    bots = {CUSTOMER_TOKEN: FakeBot(), ADMIN_TOKEN: FakeBot()}

    class _Bot(FakeBot):  # a class, not a function: telegram.ext subclasses Bot
        def __new__(cls, token=None):
            return bots[token]

        def __init__(self, token=None):
            pass

    monkeypatch.setattr(telegram, "Bot", _Bot)
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", CUSTOMER_TOKEN)
    monkeypatch.setenv("TELEGRAM_ADMIN_BOT_TOKEN", ADMIN_TOKEN)
    monkeypatch.setenv("TELEGRAM_WEBHOOK_SECRET", SECRET)
    monkeypatch.setenv("NOTIFY_TELEGRAM_CHAT_IDS", str(LUIGI))
    monkeypatch.delenv("ADMIN_TELEGRAM_IDS", raising=False)
    monkeypatch.delenv("GATEWAY_SYNC_REPLY", raising=False)
    monkeypatch.setattr(api, "_adapter", api.PipelineAdapter(queue_dir=str(tmp_path)))
    api._adapter.store.put(_job())
    return TestClient(api.app, headers={HEADER: SECRET}), bots, api._adapter.store


def test_admin_route_handles_a_button_press_on_the_admin_bot(hook):
    c, bots, store = hook
    r = c.post("/webhook/telegram-admin", json={"callback_query": _cb(encode_callback("approve", "abc123"))})
    assert r.status_code == 200 and store.get("abc123")["status"] == "approved"
    assert bots[ADMIN_TOKEN].answered and not bots[CUSTOMER_TOKEN].answered
    assert "approvata" in bots[CUSTOMER_TOKEN].to(FRIEND)[0].lower()  # the customer is told by the customer bot
    assert not bots[ADMIN_TOKEN].to(FRIEND)


def test_admin_route_handles_a_command_and_never_creates_a_job(hook):
    c, bots, store = hook
    c.post("/webhook/telegram-admin", json={"message": _msg("/pending")})
    assert bots[ADMIN_TOKEN].to(LUIGI)
    assert not store.list_by_status("queued")


def test_admin_route_ignores_ordinary_text_instead_of_queueing_it(hook):
    c, bots, store = hook
    r = c.post("/webhook/telegram-admin", json={"message": _msg("voglio un sito")})
    assert r.status_code == 200 and not store.list_by_status("queued")
    assert not bots[ADMIN_TOKEN].sent and not bots[CUSTOMER_TOKEN].sent


def test_admin_route_ignores_a_stranger(hook):
    c, bots, store = hook
    c.post("/webhook/telegram-admin", json={"callback_query": {**_cb(encode_callback("approve", "abc123")), "from": {"id": FRIEND}}})
    c.post("/webhook/telegram-admin", json={"message": _msg("/approve abc123 1", from_id=FRIEND)})
    assert store.get("abc123")["status"] == "needs_review"
    assert not bots[CUSTOMER_TOKEN].sent


def test_admin_route_requires_the_secret(hook):
    c, bots, store = hook
    body = {"callback_query": _cb(encode_callback("approve", "abc123"))}
    assert c.post("/webhook/telegram-admin", json=body, headers={HEADER: ""}).status_code == 403
    assert c.post("/webhook/telegram-admin", json=body, headers={HEADER: "wrong"}).status_code == 403
    assert store.get("abc123")["status"] == "needs_review"


def test_admin_route_is_off_without_a_configured_secret(hook, monkeypatch):
    c, bots, store = hook
    monkeypatch.delenv("TELEGRAM_WEBHOOK_SECRET")
    r = c.post("/webhook/telegram-admin", json={"callback_query": _cb(encode_callback("approve", "abc123"))})
    assert r.status_code == 503 and store.get("abc123")["status"] == "needs_review"


def test_admin_route_is_off_without_the_admin_bot(hook, monkeypatch):
    c, bots, store = hook
    monkeypatch.delenv("TELEGRAM_ADMIN_BOT_TOKEN")
    assert c.post("/webhook/telegram-admin", json={"message": _msg("/pending")}).status_code == 503


def test_admin_route_needs_the_customer_bot_too(hook, monkeypatch):
    """Without it the customer would be answered by the admin bot, which they never started."""
    c, bots, store = hook
    monkeypatch.delenv("TELEGRAM_BOT_TOKEN")
    assert c.post("/webhook/telegram-admin", json={"message": _msg("/pending")}).status_code == 503


def test_customer_route_gives_luigi_no_admin_powers_once_the_admin_bot_exists(hook):
    c, bots, store = hook
    c.post("/webhook/telegram", json={"callback_query": _cb(encode_callback("approve", "abc123"))})
    assert store.get("abc123")["status"] == "needs_review"
    r = c.post("/webhook/telegram", json={"message": _msg("/pending")})
    assert r.status_code == 200 and not store.list_by_status("queued")
    assert "non disponibile" in bots[CUSTOMER_TOKEN].to(LUIGI)[0].lower()


def test_customer_route_treats_luigis_test_request_as_a_normal_request(hook):
    c, bots, store = hook
    c.post("/webhook/telegram", json={"message": _msg("voglio un sito", from_id=LUIGI)})
    assert any("Ricevuto" in t for t in bots[CUSTOMER_TOKEN].to(LUIGI))
    assert not bots[ADMIN_TOKEN].sent  # the admin bot stays out of his customer chat


def test_customer_route_keeps_admin_powers_when_there_is_no_admin_bot(hook, monkeypatch):
    c, bots, store = hook
    monkeypatch.delenv("TELEGRAM_ADMIN_BOT_TOKEN")
    c.post("/webhook/telegram", json={"callback_query": _cb(encode_callback("approve", "abc123"))})
    assert store.get("abc123")["status"] == "approved"
