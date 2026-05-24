"""tests/test_gateway_pablo.py — Pablo track: adapter, middleware, API endpoint."""

import json
import os
import tempfile
import time

import pytest
from fastapi.testclient import TestClient

from gateway.middleware import check_rate_limit, verify_hmac
from gateway.pipeline_adapter import PipelineAdapter


# ── PipelineAdapter ──────────────────────────────────────────────────────────

class TestPipelineAdapter:
    def setup_method(self):
        self.tmp = tempfile.mkdtemp()
        self.adapter = PipelineAdapter(queue_dir=self.tmp)

    def test_submit_returns_job_id(self):
        result = self.adapter.submit("Build me a website", "api", {})
        assert result["status"] == "queued"
        assert result["job_id"] is not None
        assert len(result["job_id"]) == 10

    def test_submit_writes_job_file(self):
        result = self.adapter.submit("Make a PDF", "api", {})
        job_file = (self.adapter.queue_dir / f"{result['job_id']}.json")
        assert job_file.exists()
        job = json.loads(job_file.read_text())
        assert job["text"] == "Make a PDF"
        assert job["channel"] == "api"

    def test_submit_sanitizes_control_chars(self):
        result = self.adapter.submit("Hello\x00\x01world", "api", {})
        job = self.adapter.get_status(result["job_id"])
        assert "\x00" not in job["text"]
        assert "Helloworld" in job["text"]

    def test_submit_truncates_long_text(self):
        long_text = "a" * 5000
        result = self.adapter.submit(long_text, "api", {})
        job = self.adapter.get_status(result["job_id"])
        assert len(job["text"]) == 4000

    def test_submit_rejects_empty_text(self):
        result = self.adapter.submit("   ", "api", {})
        assert result["status"] == "error"
        assert result["job_id"] is None

    def test_submit_rejects_unknown_channel(self):
        result = self.adapter.submit("hello", "fax", {})
        assert result["status"] == "error"

    def test_get_status_not_found(self):
        result = self.adapter.get_status("nonexistent00")
        assert result["status"] == "not_found"

    def test_list_pending(self):
        self.adapter.submit("job one", "api", {})
        self.adapter.submit("job two", "streamlit", {})
        pending = self.adapter.list_pending()
        assert len(pending) == 2

    def test_metadata_not_logged_verbosely(self):
        result = self.adapter.submit("test", "telegram", {"user_id": 12345, "chat_id": 67890})
        job = self.adapter.get_status(result["job_id"])
        assert "user_id" in job["metadata"]
        assert "text_length" in job["metadata"]
        assert "timestamp" in job["metadata"]


# ── Middleware ───────────────────────────────────────────────────────────────

class TestVerifyHmac:
    def test_valid_signature(self, monkeypatch):
        import hashlib, hmac as _hmac
        monkeypatch.setenv("GATEWAY_HMAC_SECRET", "test-secret")
        payload = b"hello world"
        sig = _hmac.new(b"test-secret", payload, hashlib.sha256).hexdigest()
        assert verify_hmac(payload, sig)

    def test_invalid_signature(self, monkeypatch):
        monkeypatch.setenv("GATEWAY_HMAC_SECRET", "test-secret")
        assert not verify_hmac(b"hello", "bad-sig")

    def test_missing_secret_returns_false(self, monkeypatch):
        monkeypatch.delenv("GATEWAY_HMAC_SECRET", raising=False)
        assert not verify_hmac(b"hello", "anything")


class TestRateLimit:
    def test_allows_under_limit(self):
        ip = f"test-ip-{time.time()}"
        for _ in range(10):
            assert check_rate_limit(ip, limit=10, window=60.0)

    def test_blocks_over_limit(self):
        ip = f"test-ip-{time.time()}-block"
        for _ in range(10):
            check_rate_limit(ip, limit=10, window=60.0)
        assert not check_rate_limit(ip, limit=10, window=60.0)

    def test_different_ips_are_independent(self):
        ip_a = f"ip-a-{time.time()}"
        ip_b = f"ip-b-{time.time()}"
        for _ in range(10):
            check_rate_limit(ip_a, limit=10, window=60.0)
        assert check_rate_limit(ip_b, limit=10, window=60.0)


# ── FastAPI endpoints ────────────────────────────────────────────────────────

@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setenv("GATEWAY_HMAC_SECRET", "test-secret")
    import gateway.api as api_module
    api_module._adapter = PipelineAdapter(queue_dir=str(tmp_path))
    return TestClient(api_module.app)


class TestApiEndpoints:
    def test_health(self, client):
        r = client.get("/health")
        assert r.status_code == 200
        assert r.json()["status"] == "ok"

    def test_submit_valid(self, client):
        r = client.post("/submit", json={"text": "Build me a chatbot"})
        assert r.status_code == 202
        data = r.json()
        assert data["status"] == "queued"
        assert data["job_id"]

    def test_submit_empty_text(self, client):
        r = client.post("/submit", json={"text": "  "})
        assert r.status_code == 422

    def test_submit_invalid_channel(self, client):
        r = client.post("/submit", json={"text": "hello", "channel": "fax"})
        assert r.status_code == 422

    def test_status_not_found(self, client):
        r = client.get("/status/doesnotexist")
        assert r.status_code == 404

    def test_status_found(self, client):
        r = client.post("/submit", json={"text": "make a PDF"})
        job_id = r.json()["job_id"]
        r2 = client.get(f"/status/{job_id}")
        assert r2.status_code == 200
        assert r2.json()["job_id"] == job_id
