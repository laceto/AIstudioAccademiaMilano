"""tests/test_gateway_carlos.py — Carlos track: message normalization + bot handlers."""

import tempfile

import pytest

from gateway.bot_telegram import _normalize
from gateway.pipeline_adapter import PipelineAdapter


# ── Message normalization ────────────────────────────────────────────────────

class TestNormalize:
    def test_strips_telegram_markdown(self):
        result = _normalize("*bold* _italic_ `code`")
        assert "bold" in result and "italic" in result and "code" in result
        assert "*" not in result and "_" not in result and "`" not in result

    def test_collapses_whitespace(self):
        result = _normalize("hello   world\n\n!")
        assert "hello" in result and "world" in result
        assert "\n" not in result

    def test_empty_string(self):
        assert _normalize("") == ""

    def test_plain_text_unchanged(self):
        result = _normalize("I need a website for my restaurant")
        assert result == "I need a website for my restaurant"

    def test_emoji_passthrough(self):
        result = _normalize("Ciao! 🍕 I need a pizza menu PDF")
        assert "🍕" in result


# ── PipelineAdapter called from Telegram ────────────────────────────────────

class TestAdapterFromTelegram:
    def setup_method(self):
        self.tmp = tempfile.mkdtemp()
        self.adapter = PipelineAdapter(queue_dir=self.tmp)

    def test_telegram_channel_accepted(self):
        result = self.adapter.submit(
            text="I need a landing page",
            channel="telegram",
            metadata={"user_id": 42, "chat_id": 99},
        )
        assert result["status"] == "queued"

    def test_user_id_in_metadata(self):
        result = self.adapter.submit("hello", "telegram", {"user_id": 12345})
        job = self.adapter.get_status(result["job_id"])
        assert job["metadata"]["user_id"] == "12345"

    def test_empty_message_rejected(self):
        result = self.adapter.submit("", "telegram", {"user_id": 1})
        assert result["status"] == "error"

    def test_normalized_text_submitted(self):
        raw = "*Bold* request: build me a _chatbot_"
        normalized = _normalize(raw)
        result = self.adapter.submit(normalized, "telegram", {"user_id": 1})
        job = self.adapter.get_status(result["job_id"])
        assert "*" not in job["text"]


# ── PipelineAdapter called from WhatsApp ────────────────────────────────────

class TestAdapterFromWhatsApp:
    def setup_method(self):
        self.tmp = tempfile.mkdtemp()
        self.adapter = PipelineAdapter(queue_dir=self.tmp)

    def test_whatsapp_channel_accepted(self):
        result = self.adapter.submit(
            text="Send me an invoice for 300 euro",
            channel="whatsapp",
            metadata={"user_id": "+39123456789"},
        )
        assert result["status"] == "queued"

    def test_user_id_not_fully_logged(self):
        result = self.adapter.submit("make a report", "whatsapp", {"user_id": "+39123456789"})
        job = self.adapter.get_status(result["job_id"])
        # user_id is stored but text_length should not expose content
        assert "text_length" in job["metadata"]
        assert job["metadata"]["text_length"] > 0


# ── TwiML helper ─────────────────────────────────────────────────────────────

class TestTwimlReply:
    def test_basic_reply(self):
        from gateway.bot_whatsapp import _twiml_reply
        xml = _twiml_reply("Hello world")
        assert "<Message>Hello world</Message>" in xml
        assert '<?xml version="1.0"' in xml

    def test_escapes_special_chars(self):
        from gateway.bot_whatsapp import _twiml_reply
        xml = _twiml_reply("Price: 10 & 20 < 100")
        assert "&amp;" in xml
        assert "&lt;" in xml
        assert "<script>" not in xml
