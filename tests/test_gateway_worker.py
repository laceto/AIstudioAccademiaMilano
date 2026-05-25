"""tests/test_gateway_worker.py — Queue worker: classification, reply, job lifecycle."""

import asyncio
import json
import tempfile

import pytest

from gateway.worker import QueueWorker


@pytest.fixture
def tmp_worker(tmp_path):
    return QueueWorker(queue_dir=str(tmp_path))


# ── classify (no API key → fallback) ────────────────────────────────────────

class TestClassifyFallback:
    def test_no_api_key_returns_unknown(self, tmp_worker, monkeypatch):
        monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
        monkeypatch.delenv("OPENAI_API_KEY", raising=False)
        w = QueueWorker(queue_dir=str(tmp_worker.queue_dir))
        result = asyncio.run(w.classify("Build me a chatbot"))
        assert result["product_type"] == "unknown_product"
        assert result["needs_review"] is True
        assert result["confidence"] == 0.0

    def test_summary_truncated_to_80_chars(self, tmp_worker):
        long_text = "x" * 200
        result = asyncio.run(tmp_worker.classify(long_text))
        assert len(result["summary"]) <= 80


# ── _build_reply ─────────────────────────────────────────────────────────────

class TestBuildReply:
    def _job(self, tmp_worker):
        return {"job_id": "abc12345", "text": "test request", "channel": "api", "metadata": {}}

    def test_known_product_classified(self, tmp_worker):
        cls = {"product_type": "chatbot_app", "confidence": 0.95, "summary": "Chatbot", "needs_review": False}
        status, reply = tmp_worker._build_reply(self._job(tmp_worker), cls)
        assert status == "classified"
        assert "19.90" in reply
        assert "Chatbot App" in reply

    def test_unknown_product_needs_review(self, tmp_worker):
        cls = {"product_type": "unknown_product", "confidence": 0.5, "summary": "Flying car", "needs_review": True}
        status, reply = tmp_worker._build_reply(self._job(tmp_worker), cls)
        assert status == "needs_review"
        assert "Luigi" in reply

    def test_low_confidence_needs_review(self, tmp_worker):
        cls = {"product_type": "chatbot_app", "confidence": 0.4, "summary": "Something", "needs_review": True}
        status, _ = tmp_worker._build_reply(self._job(tmp_worker), cls)
        assert status == "needs_review"

    def test_job_id_in_reply(self, tmp_worker):
        cls = {"product_type": "pdf_document", "confidence": 0.9, "summary": "A PDF", "needs_review": False}
        _, reply = tmp_worker._build_reply(self._job(tmp_worker), cls)
        assert "abc12345" in reply

    def test_all_known_products_classified(self, tmp_worker):
        known = [
            "static_landing_page", "premium_landing_page", "commercial_landing_page",
            "pdf_document", "invoice_pdf", "strategic_report", "chatbot_app",
            "email_delivery", "rag_knowledge_base", "calendar_integration",
            "weather_dashboard", "agent_deploy_streamlit",
        ]
        job = self._job(tmp_worker)
        for product in known:
            cls = {"product_type": product, "confidence": 0.95, "summary": "x", "needs_review": False}
            status, _ = tmp_worker._build_reply(job, cls)
            assert status == "classified", f"{product} should be classified"


# ── _process job lifecycle ────────────────────────────────────────────────────

class TestProcessLifecycle:
    def test_queued_job_reaches_terminal_state(self, tmp_path):
        from gateway.pipeline_adapter import PipelineAdapter
        adapter = PipelineAdapter(queue_dir=str(tmp_path))
        r = adapter.submit("Build me a chatbot", "api", {})
        job_id = r["job_id"]

        worker = QueueWorker(queue_dir=str(tmp_path))

        async def _run():
            job = adapter.get_status(job_id)
            await worker._process(job)
            updated = adapter.get_status(job_id)
            assert updated["status"] in ("classified", "needs_review", "error")
            assert updated.get("processed_at") is not None
            assert updated.get("result") is not None

        asyncio.run(_run())

    def test_multiple_jobs_all_processed(self, tmp_path):
        from gateway.pipeline_adapter import PipelineAdapter
        adapter = PipelineAdapter(queue_dir=str(tmp_path))
        adapter.submit("job one", "api", {})
        adapter.submit("job two", "streamlit", {})
        adapter.submit("job three", "telegram", {"user_id": 1, "chat_id": 999})

        worker = QueueWorker(queue_dir=str(tmp_path))

        async def _run():
            pending = adapter.list_pending()
            assert len(pending) == 3
            await asyncio.gather(*[worker._process(j) for j in pending])
            assert adapter.list_pending() == []

        asyncio.run(_run())

    def test_processed_at_is_iso_timestamp(self, tmp_path):
        from gateway.pipeline_adapter import PipelineAdapter
        from datetime import datetime
        adapter = PipelineAdapter(queue_dir=str(tmp_path))
        r = adapter.submit("make a PDF", "api", {})
        worker = QueueWorker(queue_dir=str(tmp_path))

        async def _run():
            job = adapter.get_status(r["job_id"])
            await worker._process(job)
            updated = adapter.get_status(r["job_id"])
            ts = updated.get("processed_at", "")
            datetime.fromisoformat(ts)  # raises ValueError if invalid

        asyncio.run(_run())

    def test_classification_stored_in_job(self, tmp_path):
        from gateway.pipeline_adapter import PipelineAdapter
        adapter = PipelineAdapter(queue_dir=str(tmp_path))
        r = adapter.submit("need a chatbot", "api", {})
        worker = QueueWorker(queue_dir=str(tmp_path))

        async def _run():
            job = adapter.get_status(r["job_id"])
            await worker._process(job)
            updated = adapter.get_status(r["job_id"])
            assert "classification" in updated

        asyncio.run(_run())
