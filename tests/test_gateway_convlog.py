"""Tests for gateway/convlog.py — per-session message logging.

Cloud Run keeps stdout in Cloud Logging, so these lines are the only record of
what a user asked and what the bot answered. They must be one line each, keyed
by chat_id, and must never carry the bot token.
"""

import io
import logging

from gateway import convlog


def _capture():
    buf = io.StringIO()
    handler = logging.StreamHandler(buf)
    handler.setFormatter(logging.Formatter("%(message)s"))
    lg = logging.getLogger("gateway.conversation")
    lg.addHandler(handler)
    return buf, lg, handler


def test_log_message_has_direction_chat_and_text():
    buf, lg, h = _capture()
    try:
        convlog.log_message("in", 42, "Ciao, vorrei un sito")
    finally:
        lg.removeHandler(h)
    line = buf.getvalue().strip()
    assert "dir=in" in line and "chat=42" in line and "Ciao, vorrei un sito" in line


def test_log_message_is_one_line_even_with_newlines():
    buf, lg, h = _capture()
    try:
        convlog.log_message("out", 7, "riga1\nriga2\r\nriga3")
    finally:
        lg.removeHandler(h)
    assert len(buf.getvalue().strip().splitlines()) == 1


def test_log_message_truncates_long_text():
    buf, lg, h = _capture()
    try:
        convlog.log_message("in", 1, "x" * 5000)
    finally:
        lg.removeHandler(h)
    assert len(buf.getvalue()) < convlog.MAX_CHARS + 200
    assert "truncated" in buf.getvalue()


def test_conversation_logger_is_independent_of_root_config():
    lg = logging.getLogger("gateway.conversation")
    assert lg.level == logging.INFO
    assert lg.propagate is False
    assert lg.handlers, "needs its own stdout handler: root logging is configured late"


def test_silence_http_loggers_hides_token_bearing_urls():
    logging.getLogger("httpx").setLevel(logging.INFO)
    convlog.silence_http_loggers()
    assert logging.getLogger("httpx").level >= logging.WARNING
    assert logging.getLogger("httpcore").level >= logging.WARNING


# ── Wired into the Telegram webhook ──────────────────────────────────────────


class _FakeBot:
    sent: list = []

    def __init__(self, token):
        pass

    async def send_message(self, chat_id, text, **kwargs):
        _FakeBot.sent.append((chat_id, text))


def _post_update(monkeypatch, tmp_path, text):
    from fastapi.testclient import TestClient

    import telegram

    from gateway import api

    _FakeBot.sent = []
    monkeypatch.setattr(telegram, "Bot", _FakeBot)
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "123:fake-token")
    monkeypatch.delenv("GATEWAY_SYNC_REPLY", raising=False)
    monkeypatch.setattr(api, "_adapter", api.PipelineAdapter(queue_dir=str(tmp_path)))
    update = {"message": {"text": text, "chat": {"id": 555}, "from": {"id": 9}}}
    return TestClient(api.app).post("/webhook/telegram", json=update)


def test_webhook_logs_inbound_and_outbound(monkeypatch, tmp_path):
    buf, lg, h = _capture()
    try:
        resp = _post_update(monkeypatch, tmp_path, "Vorrei una landing page")
    finally:
        lg.removeHandler(h)
    assert resp.status_code == 200
    out = buf.getvalue()
    assert "dir=in chat=555" in out and "Vorrei una landing page" in out
    assert "dir=out chat=555" in out and "Ricevuto" in out


def test_webhook_logs_start_command_reply(monkeypatch, tmp_path):
    buf, lg, h = _capture()
    try:
        _post_update(monkeypatch, tmp_path, "/start")
    finally:
        lg.removeHandler(h)
    out = buf.getvalue()
    assert "dir=in chat=555" in out and "/start" in out
    assert "dir=out chat=555" in out and "Benvenuto" in out
