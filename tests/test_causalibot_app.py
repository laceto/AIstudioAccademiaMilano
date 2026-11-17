"""Offline tests for causalibot.app: webhook secret, only Luigi, confirm-before-save, undo. No network."""
from datetime import date, datetime, timezone
from decimal import Decimal

import pytest
from fastapi.testclient import TestClient

from causalibot.app import create_app
from causalibot.store import MemoryStore

SECRET = "s" * 40
LUIGI = 111
NOW = datetime(2026, 11, 17, 10, 0, tzinfo=timezone.utc)


class FakeTelegram:
    def __init__(self):
        self.sent, self.edited, self.answered = [], [], []

    async def send_message(self, chat_id, text, keyboard=None):
        self.sent.append((chat_id, text, keyboard))
        return {"message_id": 7}

    async def edit_message(self, chat_id, message_id, text, keyboard=None):
        self.edited.append((chat_id, message_id, text, keyboard))

    async def answer_callback(self, callback_id, text=""):
        self.answered.append(callback_id)


@pytest.fixture
def env():
    store, tg = MemoryStore(), FakeTelegram()
    app = create_app(store=store, telegram=tg, secret=SECRET, allowed_chat_id=LUIGI, now=lambda: NOW)
    return TestClient(app), store, tg


def post(client, body, secret=SECRET):
    return client.post("/webhook/telegram-causali", json=body, headers={"X-Telegram-Bot-Api-Secret-Token": secret})


def msg(text, chat=LUIGI):
    return {"message": {"message_id": 1, "chat": {"id": chat}, "from": {"id": chat}, "text": text}}


def tap(data, chat=LUIGI):
    return {"callback_query": {"id": "cb1", "data": data, "from": {"id": chat},
                               "message": {"message_id": 7, "chat": {"id": chat}}}}


def buttons(keyboard):
    return [b for row in keyboard for b in row]


def draft_key(tg):
    return next(b["callback_data"] for b in buttons(tg.sent[-1][2]) if b["callback_data"].startswith("s:"))[2:]


def test_health(env):
    client, _, _ = env
    assert client.get("/health").json() == {"status": "ok"}


def test_wrong_secret_is_403(env):
    client, store, tg = env
    assert post(client, msg("250 credem pulizie"), secret="x" * 40).status_code == 403
    assert tg.sent == [] and store.recent() == []


def test_not_configured_is_503():
    client = TestClient(create_app(store=MemoryStore(), telegram=FakeTelegram(), secret="", allowed_chat_id=LUIGI))
    assert post(client, msg("ciao")).status_code == 503


def test_stranger_is_ignored_without_reply(env):
    client, store, tg = env
    assert post(client, msg("250 credem pulizie", chat=999)).status_code == 200
    assert post(client, tap("s:abc", chat=999)).status_code == 200
    assert tg.sent == [] and tg.edited == [] and tg.answered == [] and store.recent() == []


def test_message_makes_a_card_and_saves_nothing(env):
    client, store, tg = env
    post(client, msg("250 credem pulizie Valeria"))
    chat, text, keyboard = tg.sent[-1]
    assert chat == LUIGI and "17/11/2026" in text and "Credem" in text and "-250,00" in text
    assert "Pulizie Valeria" in text
    assert {b["text"] for b in buttons(keyboard)} == {"Salva", "Categoria ▸", "Annulla"}
    assert store.recent() == []


def test_save_only_after_salva(env):
    client, store, tg = env
    post(client, msg("250 credem pulizie Valeria"))
    post(client, tap(f"s:{draft_key(tg)}"))
    saved = store.recent()
    assert len(saved) == 1 and saved[0].amount == Decimal("-250.00") and saved[0].bank == "credem"
    assert saved[0].day == date(2026, 11, 17) and saved[0].allegati == []
    assert "Salvata" in tg.edited[-1][2]


def test_second_tap_on_salva_does_not_duplicate(env):
    client, store, tg = env
    post(client, msg("250 credem pulizie Valeria"))
    key = draft_key(tg)
    post(client, tap(f"s:{key}"))
    post(client, tap(f"s:{key}"))
    assert len(store.recent()) == 1


def test_annulla_button_drops_the_draft(env):
    client, store, tg = env
    post(client, msg("250 credem pulizie Valeria"))
    key = draft_key(tg)
    post(client, tap(f"x:{key}"))
    post(client, tap(f"s:{key}"))
    assert store.recent() == []


def test_category_menu_changes_category(env):
    client, store, tg = env
    post(client, msg("250 credem pulizie Valeria"))
    key = draft_key(tg)
    post(client, tap(f"c:{key}"))
    pick = buttons(tg.edited[-1][3])[0]
    post(client, tap(pick["callback_data"]))
    post(client, tap(f"s:{key}"))
    assert store.recent()[0].category == pick["text"]


def test_missing_bank_gets_an_explanation_and_no_draft(env):
    client, store, tg = env
    post(client, msg("pulizie 250"))
    assert "banca" in tg.sent[-1][1].lower() and tg.sent[-1][2] is None
    assert store._drafts == {}


def test_ultime_and_annulla_command(env):
    client, store, tg = env
    post(client, msg("250 credem pulizie Valeria"))
    post(client, tap(f"s:{draft_key(tg)}"))
    post(client, msg("/ultime"))
    assert "Pulizie Valeria" in tg.sent[-1][1]
    post(client, msg("/annulla"))
    assert store.recent() == [] and "tolta" in tg.sent[-1][1].lower()


def test_annulla_with_nothing_recent(env):
    client, _, tg = env
    post(client, msg("/annulla"))
    assert "niente" in tg.sent[-1][1].lower()


def test_help_lists_bank_requirement(env):
    client, _, tg = env
    post(client, msg("/help"))
    assert "credem" in tg.sent[-1][1] and "banca" in tg.sent[-1][1].lower()


def test_photo_is_not_supported_yet(env):
    client, store, tg = env
    post(client, {"message": {"message_id": 2, "chat": {"id": LUIGI}, "from": {"id": LUIGI}, "photo": [{}]}})
    assert "foto" in tg.sent[-1][1].lower() and store.recent() == []
