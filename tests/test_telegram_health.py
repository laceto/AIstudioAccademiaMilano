"""Tests for scripts/check_telegram.py — the Telegram channel doctor.

Covers the failure mode that actually took the pipeline bot down: a webhook
registered on the polling bot's token, which makes Telegram refuse getUpdates
with a 409 and leaves the bot silently unreachable.
"""

import pytest

from scripts import check_telegram as ct


def _stub(webhook_url="", pending=0, last_error=None):
    """Replace ct._call with canned getMe / getWebhookInfo responses."""

    def _call(token, method):
        if method == "getMe":
            return {"ok": True, "result": {"username": "aistudiomilano_bot"}}
        result = {"url": webhook_url, "pending_update_count": pending}
        if last_error:
            result["last_error_message"] = last_error
            result["last_error_date"] = 1748500000
        return {"ok": True, "result": result}

    return _call


@pytest.fixture
def token_env(monkeypatch):
    monkeypatch.setattr(ct, "_ENV_FILE", __file__)  # never read the real .env
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "111:pipeline")
    monkeypatch.setenv("TELEGRAM_RAG_BOT_TOKEN", "222:rag")


class TestBotId:
    def test_returns_public_prefix_only(self):
        assert ct._bot_id("1234567890:AAsecretHalf") == "1234567890"

    def test_never_leaks_secret_half(self):
        assert "AAsecretHalf" not in ct._bot_id("1234567890:AAsecretHalf")

    def test_malformed_token(self):
        assert ct._bot_id("nocolon") == "?"


class TestPipelineBot:
    def test_polling_mode_is_healthy(self, token_env, monkeypatch):
        monkeypatch.setattr(ct, "_call", _stub())
        errors, warnings = [], []
        ct.check("pipeline", set(), errors, warnings)
        assert errors == []

    def test_webhook_on_polling_bot_is_an_error(self, token_env, monkeypatch):
        monkeypatch.setattr(ct, "_call", _stub(webhook_url="https://x.up.railway.app/webhook/telegram"))
        errors, warnings = [], []
        ct.check("pipeline", set(), errors, warnings)
        assert len(errors) == 1
        assert "409" in errors[0]

    def test_webhook_accepted_when_expected(self, token_env, monkeypatch):
        monkeypatch.setattr(ct, "_call", _stub(webhook_url="https://x.up.railway.app/webhook/telegram"))
        errors, warnings = [], []
        ct.check("pipeline", {"pipeline"}, errors, warnings)
        assert errors == []

    def test_missing_token_is_an_error(self, token_env, monkeypatch):
        monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "")
        errors, warnings = [], []
        ct.check("pipeline", set(), errors, warnings)
        assert "not set" in errors[0]

    def test_placeholder_token_is_an_error(self, token_env, monkeypatch):
        monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "your-bot-token-here")
        errors, warnings = [], []
        ct.check("pipeline", set(), errors, warnings)
        assert "not set" in errors[0]

    def test_queued_updates_warn(self, token_env, monkeypatch):
        monkeypatch.setattr(ct, "_call", _stub(pending=7))
        errors, warnings = [], []
        ct.check("pipeline", set(), errors, warnings)
        assert errors == []
        assert "7 update(s)" in warnings[0]


class TestRagBot:
    def test_missing_webhook_is_an_error(self, token_env, monkeypatch):
        monkeypatch.setattr(ct, "_call", _stub())
        errors, warnings = [], []
        ct.check("rag", set(), errors, warnings)
        assert "no webhook registered" in errors[0]

    def test_webhook_present_is_healthy(self, token_env, monkeypatch):
        monkeypatch.setattr(ct, "_call", _stub(webhook_url="https://x.up.railway.app/webhook/telegram"))
        errors, warnings = [], []
        ct.check("rag", set(), errors, warnings)
        assert errors == []

    def test_telegram_delivery_error_surfaces(self, token_env, monkeypatch):
        monkeypatch.setattr(
            ct, "_call", _stub(webhook_url="https://x.up.railway.app/webhook/telegram",
                               last_error="Connection refused")
        )
        errors, warnings = [], []
        ct.check("rag", set(), errors, warnings)
        assert any("Connection refused" in e for e in errors)


class TestTokenCollision:
    def test_shared_token_between_bots_is_an_error(self, token_env, monkeypatch):
        monkeypatch.setenv("TELEGRAM_RAG_BOT_TOKEN", "111:pipeline")  # same as pipeline
        monkeypatch.setattr(ct, "_call", _stub(webhook_url="https://x.up.railway.app/webhook/telegram"))
        monkeypatch.setattr("sys.argv", ["check_telegram.py"])
        assert ct.main() == 1

    def test_distinct_tokens_correctly_wired_pass(self, token_env, monkeypatch):
        def _call(token, method):
            if method == "getMe":
                return {"ok": True, "result": {"username": "bot"}}
            # pipeline polls, rag uses a webhook
            url = "" if token == "111:pipeline" else "https://x.up.railway.app/webhook/telegram"
            return {"ok": True, "result": {"url": url, "pending_update_count": 0}}

        monkeypatch.setattr(ct, "_call", _call)
        monkeypatch.setattr("sys.argv", ["check_telegram.py"])
        assert ct.main() == 0
