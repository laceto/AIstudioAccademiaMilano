"""Tests for gateway/privacy.py — the privacy notice shown on /start and /privacy.

The notice is information, not a consent gate. Every number in it must come from the code that
enforces it (retention_days, convlog.MAX_CHARS), so these tests move the settings and check the
text follows.
"""

import re
from pathlib import Path

import pytest

from gateway import convlog, privacy

TELEGRAM_LIMIT = 4096


@pytest.fixture(autouse=True)
def _clean_env(monkeypatch):
    monkeypatch.delenv("JOB_RETENTION_DAYS", raising=False)
    monkeypatch.delenv("PRIVACY_CONTACT", raising=False)
    monkeypatch.delenv("TELEGRAM_WEBHOOK_SECRET", raising=False)


# ── retention ────────────────────────────────────────────────────────────────


def test_retention_follows_the_setting(monkeypatch):
    monkeypatch.setenv("JOB_RETENTION_DAYS", "45")
    text = privacy.privacy_text()
    assert "45 giorni" in text
    assert "90" not in text  # no stray default contradicting the setting


def test_retention_default_is_the_retention_module_default():
    assert "90 giorni" in privacy.privacy_text()


def test_retention_30_is_shown(monkeypatch):
    monkeypatch.setenv("JOB_RETENTION_DAYS", "30")
    assert "30 giorni" in privacy.privacy_text()


def test_log_retention_is_stated_apart_from_job_retention(monkeypatch):
    monkeypatch.setenv("JOB_RETENTION_DAYS", "45")
    text = privacy.privacy_text()
    assert f"{privacy.LOG_RETENTION_DAYS} giorni" in text
    assert "Cloud Logging" in text


def test_logged_characters_come_from_convlog():
    assert f"{convlog.MAX_CHARS} caratteri" in privacy.privacy_text()


# ── content ──────────────────────────────────────────────────────────────────


@pytest.mark.parametrize(
    "needle",
    [
        "Cloud Run",
        "Firestore",
        "europe-west8",
        "Cloud Logging",
        "Cloud Tasks",
        "europe-west6",
        "OpenAI",
        "Telegram",
        "Gmail",
        "Garante",
        "accesso",
        "rettifica",
        "cancellazione",
    ],
)
def test_privacy_text_mentions(needle):
    assert needle.lower() in privacy.privacy_text().lower()


def test_privacy_text_says_what_is_stored_and_who_sees_it():
    text = privacy.privacy_text().lower()
    for needle in ("testo dei messaggi", "id", "classificazione", "risultato", "titolare"):
        assert needle in text


def test_privacy_text_is_not_a_consent_gate():
    text = privacy.privacy_text().lower()
    assert "accetto" not in text and "acconsento" not in text and "consenso" not in text


# ── contact ──────────────────────────────────────────────────────────────────


def test_contact_uses_the_env_setting(monkeypatch):
    monkeypatch.setenv("PRIVACY_CONTACT", "privacy@example.it")
    text = privacy.privacy_text()
    assert "privacy@example.it" in text
    assert "in questa chat" not in text


def test_contact_falls_back_to_the_chat_honestly():
    text = privacy.privacy_text()
    assert "in questa chat" in text
    assert "non" in text.lower() and "indirizzo" in text.lower()


def test_blank_contact_counts_as_unset(monkeypatch):
    monkeypatch.setenv("PRIVACY_CONTACT", "   ")
    assert "in questa chat" in privacy.privacy_text()


def test_handle_contact_is_shown(monkeypatch):
    monkeypatch.setenv("PRIVACY_CONTACT", "@acetoluigi")
    assert "@acetoluigi" in privacy.privacy_text()


# ── start message ────────────────────────────────────────────────────────────


def test_start_message_keeps_welcome_content():
    text = privacy.start_message()
    assert "Benvenuto" in text
    assert "Esempi" in text
    assert "sito per il mio ristorante" in text
    assert "/ask" in text


def test_start_message_points_to_privacy():
    assert "/privacy" in privacy.start_message()


def test_start_message_is_short():
    assert len(privacy.start_message()) < 1200
    assert len(privacy.start_message()) < len(privacy.privacy_text())


@pytest.mark.parametrize("contact", ["", "privacy@example.it"])
@pytest.mark.parametrize("fn", ["start_message", "privacy_text"])
def test_messages_fit_telegram_and_have_no_placeholders(monkeypatch, fn, contact):
    monkeypatch.setenv("PRIVACY_CONTACT", contact)
    text = getattr(privacy, fn)()
    assert 0 < len(text) < TELEGRAM_LIMIT
    assert not re.search(r"\{[^}]*\}", text)
    assert "TODO" not in text


# ── wired into the Telegram webhook ──────────────────────────────────────────


class _FakeBot:
    sent: list = []
    kwargs: list = []

    def __init__(self, token):
        pass

    async def send_message(self, chat_id, text, **kwargs):
        _FakeBot.sent.append((chat_id, text))
        _FakeBot.kwargs.append(kwargs)


def _post(monkeypatch, tmp_path, text, headers=None):
    from fastapi.testclient import TestClient

    import telegram

    from gateway import api

    _FakeBot.sent, _FakeBot.kwargs = [], []
    monkeypatch.setattr(telegram, "Bot", _FakeBot)
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "123:fake-token")
    monkeypatch.delenv("GATEWAY_SYNC_REPLY", raising=False)
    monkeypatch.setattr(api, "_adapter", api.PipelineAdapter(queue_dir=str(tmp_path)))
    update = {"message": {"text": text, "chat": {"id": 555}, "from": {"id": 9}}}
    return TestClient(api.app).post("/webhook/telegram", json=update, headers=headers or {})


def test_webhook_start_has_welcome_and_privacy_pointer(monkeypatch, tmp_path):
    resp = _post(monkeypatch, tmp_path, "/start")
    assert resp.status_code == 200
    (chat, text), = _FakeBot.sent
    assert chat == 555
    assert "Benvenuto" in text and "/ask" in text and "/privacy" in text
    assert "parse_mode" not in _FakeBot.kwargs[0]
    assert list(tmp_path.iterdir()) == []


def test_webhook_privacy_returns_full_text_and_creates_no_job(monkeypatch, tmp_path):
    monkeypatch.setenv("JOB_RETENTION_DAYS", "45")
    resp = _post(monkeypatch, tmp_path, "/privacy")
    assert resp.status_code == 200
    (chat, text), = _FakeBot.sent
    assert chat == 555 and text == privacy.privacy_text()
    assert "45 giorni" in text
    assert "parse_mode" not in _FakeBot.kwargs[0]
    assert list(tmp_path.iterdir()) == []


def test_webhook_privacy_with_bot_suffix(monkeypatch, tmp_path):
    _post(monkeypatch, tmp_path, "/privacy@AIStudioMilanoBot")
    assert _FakeBot.sent[0][1] == privacy.privacy_text()
    assert list(tmp_path.iterdir()) == []


def test_webhook_privacy_is_logged_like_other_replies(monkeypatch, tmp_path):
    import io
    import logging

    buf = io.StringIO()
    handler = logging.StreamHandler(buf)
    handler.setFormatter(logging.Formatter("%(message)s"))
    lg = logging.getLogger("gateway.conversation")
    lg.addHandler(handler)
    try:
        _post(monkeypatch, tmp_path, "/privacy")
    finally:
        lg.removeHandler(handler)
    out = buf.getvalue()
    assert "dir=in chat=555" in out and "dir=out chat=555" in out


def test_webhook_privacy_still_needs_the_webhook_secret(monkeypatch, tmp_path):
    monkeypatch.setenv("TELEGRAM_WEBHOOK_SECRET", "s3cret-for-test")
    resp = _post(monkeypatch, tmp_path, "/privacy")
    assert resp.status_code == 403
    assert _FakeBot.sent == []
    resp = _post(
        monkeypatch, tmp_path, "/privacy", headers={"X-Telegram-Bot-Api-Secret-Token": "s3cret-for-test"}
    )
    assert resp.status_code == 200 and len(_FakeBot.sent) == 1


def test_normal_request_still_becomes_a_job(monkeypatch, tmp_path):
    _post(monkeypatch, tmp_path, "Vorrei una landing page")
    assert len(list(tmp_path.iterdir())) == 1


# ── compliance review round ──────────────────────────────────────────────────

ROOT = Path(__file__).resolve().parent.parent


def test_retention_wording_is_about_and_automatic(monkeypatch):
    monkeypatch.setenv("JOB_RETENTION_DAYS", "45")
    text = privacy.privacy_text()
    assert "circa 45 giorni" in text
    assert "automaticamente" in text
    assert "fino a un giorno" in text
    assert "backup" not in text.lower()


def test_owner_copies_stay_until_he_deletes_them():
    text = privacy.privacy_text()
    assert "chat Telegram del titolare" in text
    assert "casella e-mail del titolare" in text


def test_rights_section_explains_logs_and_third_parties():
    text = privacy.privacy_text()
    assert "non possono essere cancellate una per una" in text
    assert f"scadono da sole dopo {privacy.LOG_RETENTION_DAYS} giorni" in text
    assert "condizioni proprie" in text
    assert "titolare autonomo" in text


def test_automated_decisions_are_described_exactly():
    text = privacy.privacy_text()
    assert "listino fisso" in text
    assert "senza revisione umana" in text
    assert "decide il titolare" in text
    assert "nessuna decisione con effetti giuridici" in text.lower()


def test_start_message_says_out_of_catalogue_requests_are_read():
    text = privacy.start_message()
    assert "ogni richiesta fuori catalogo viene letta dal titolare" in text
    assert "quando serve rivedere" not in text


def test_runbook_exists_and_is_linked():
    body = (ROOT / "process" / "runbook_privacy_requests.md").read_text(encoding="utf-8")
    for needle in ("metadata.chat_id", "jobs", "un mese", "30 giorni", "Cloud Logging"):
        assert needle in body
    assert "gcloud" not in body
    docs = (ROOT / "docs" / "cloud-run-setup.md").read_text(encoding="utf-8")
    assert "process/runbook_privacy_requests.md" in docs


def test_todo_list_mentions_transfer_safeguards():
    src = (ROOT / "gateway" / "privacy.py").read_text(encoding="utf-8")
    assert "safeguards wording to be confirmed with a professional" in src
