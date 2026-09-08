"""Tests for scale-to-zero (Cloud Run) sync-reply mode.

On a host that freezes the container once the response is sent, the background
QueueWorker loop never advances — the user gets the "Job ID" acknowledgement and
nothing else, ever. GATEWAY_SYNC_REPLY makes the webhook classify inline instead.
"""

import asyncio
import json

import pytest

from gateway.pipeline_adapter import PipelineAdapter
from gateway.worker import QueueWorker


@pytest.fixture
def queue(tmp_path):
    return PipelineAdapter(queue_dir=str(tmp_path))


def _worker(tmp_path, classification=None, fail=False):
    w = QueueWorker(queue_dir=str(tmp_path))

    async def classify(text):
        if fail:
            raise RuntimeError("upstream down")
        return classification or {
            "intent": "landing_page_request",
            "product_type": "static_landing_page",
            "confidence": 0.95,
            "summary": "Landing page for a restaurant",
            "needs_review": False,
        }

    w.classify = classify
    return w


class TestSyncReplyFlag:
    @pytest.mark.parametrize("value", ["1", "true", "TRUE", "yes"])
    def test_enabled_values(self, monkeypatch, value):
        from gateway import api
        monkeypatch.setenv("GATEWAY_SYNC_REPLY", value)
        assert api._sync_reply_enabled() is True

    @pytest.mark.parametrize("value", ["", "0", "false", "no", "off"])
    def test_disabled_values(self, monkeypatch, value):
        from gateway import api
        monkeypatch.setenv("GATEWAY_SYNC_REPLY", value)
        assert api._sync_reply_enabled() is False

    def test_defaults_to_disabled(self, monkeypatch):
        """Unset must keep the polling behaviour — no surprise change for existing deploys."""
        from gateway import api
        monkeypatch.delenv("GATEWAY_SYNC_REPLY", raising=False)
        assert api._sync_reply_enabled() is False


class TestProcessJob:
    def test_returns_priced_reply(self, tmp_path, queue):
        submitted = queue.submit("Serve una landing page", "telegram", {"chat_id": 42})
        job = queue.get_status(submitted["job_id"])

        status, reply = asyncio.run(_worker(tmp_path).process_job(job))

        assert status == "classified"
        assert "9.90" in reply
        assert "Static Landing Page" in reply

    def test_unknown_product_needs_review(self, tmp_path, queue):
        submitted = queue.submit("Tu funzioni?", "telegram", {"chat_id": 42})
        job = queue.get_status(submitted["job_id"])

        status, reply = asyncio.run(
            _worker(
                tmp_path,
                classification={
                    "intent": "meta_question",
                    "product_type": "unknown_product",
                    "confidence": 0.4,
                    "summary": "Asking if the bot works",
                    "needs_review": True,
                },
            ).process_job(job)
        )

        assert status == "needs_review"
        assert "approvazione di Luigi" in reply

    def test_persists_result_to_queue_file(self, tmp_path, queue):
        submitted = queue.submit("Serve una landing page", "telegram", {"chat_id": 42})
        job = queue.get_status(submitted["job_id"])

        asyncio.run(_worker(tmp_path).process_job(job))

        saved = json.loads((tmp_path / f"{submitted['job_id']}.json").read_text(encoding="utf-8"))
        assert saved["status"] == "classified"
        assert saved["result"]
        assert saved["classification"]["product_type"] == "static_landing_page"

    def test_classification_failure_is_reported_not_raised(self, tmp_path, queue):
        submitted = queue.submit("Serve una landing page", "telegram", {"chat_id": 42})
        job = queue.get_status(submitted["job_id"])

        status, reply = asyncio.run(_worker(tmp_path, fail=True).process_job(job))

        assert status == "error"
        assert "upstream down" in reply

    def test_polling_path_still_notifies_telegram(self, tmp_path, queue):
        """_process must keep its old behaviour so laptop/always-on hosting is unaffected."""
        submitted = queue.submit("Serve una landing page", "telegram", {"chat_id": 42})
        job = queue.get_status(submitted["job_id"])

        w = _worker(tmp_path)
        sent = []

        async def notify(chat_id, text):
            sent.append((chat_id, text))

        w._notify_telegram = notify
        asyncio.run(w._process(job))

        assert len(sent) == 1
        assert sent[0][0] == "42"
        assert "9.90" in sent[0][1]

    def test_no_telegram_notify_on_classification_failure(self, tmp_path, queue):
        submitted = queue.submit("Serve una landing page", "telegram", {"chat_id": 42})
        job = queue.get_status(submitted["job_id"])

        w = _worker(tmp_path, fail=True)
        sent = []

        async def notify(chat_id, text):
            sent.append((chat_id, text))

        w._notify_telegram = notify
        asyncio.run(w._process(job))

        assert sent == []
