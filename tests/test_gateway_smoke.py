"""tests/test_gateway_smoke.py — 046: smoke test of the Input Gateway (scripts/gateway_smoke.py).

The smoke client talks to the gateway through a small transport function, so here it
runs against the real FastAPI app (TestClient) with a temporary file job store.
"""

import pytest
from fastapi.testclient import TestClient

import gateway.api as api_module
from gateway import middleware
from gateway.pipeline_adapter import PipelineAdapter
from scripts import gateway_smoke as smoke


KEY = "s" * 40


@pytest.fixture
def client(tmp_path, monkeypatch):
    middleware._buckets.clear()  # the rate limiter is per process; keep tests independent
    monkeypatch.delenv("GATEWAY_ALLOW_OPEN_SUBMIT", raising=False)
    monkeypatch.setenv("GATEWAY_API_KEY", KEY)
    api_module._adapter = PipelineAdapter(queue_dir=str(tmp_path))
    return TestClient(api_module.app)  # no `with`: lifespan (and its worker) does not start


def _transport(client, api_key=KEY):
    def call(method, path, body=None, key=True):
        headers = {"X-API-Key": api_key} if key and api_key else {}
        r = client.request(method, path, json=body, headers=headers)
        try:
            data = r.json()
        except ValueError:
            data = {}
        return r.status_code, data
    return call


def test_full_smoke_passes_against_real_app(client):
    checks, job_id = smoke.run_smoke(_transport(client), smoke.DEFAULT_REQUEST, wait_seconds=0)
    assert job_id
    assert all(c.ok for c in checks), [c for c in checks if not c.ok]
    names = [c.name for c in checks]
    assert names == ["health", "rejects_missing_key", "rejects_bad_channel", "submit", "status", "unknown_job_404"]


def test_wrong_key_fails_the_submit_check(client):
    checks, job_id = smoke.run_smoke(_transport(client, api_key="wrong"), "x", wait_seconds=0)
    assert job_id is None
    assert {c.name: c for c in checks}["submit"].ok is False


def test_job_is_marked_as_smoke_test(client):
    _, job_id = smoke.run_smoke(_transport(client), "Vorrei una landing page", wait_seconds=0)
    job = api_module._adapter.get_status(job_id)
    assert job["metadata"]["user_id"] == smoke.SMOKE_USER_ID
    assert job["text"] == "Vorrei una landing page"


def test_health_failure_stops_early():
    def down(method, path, body=None, key=True):
        return 503, {}
    checks, job_id = smoke.run_smoke(down, "x", wait_seconds=0)
    assert job_id is None
    assert [c.name for c in checks] == ["health"]
    assert not checks[0].ok


def test_wait_until_classified_accepts_expected_status():
    states = iter(["queued", "processing", "needs_review"])

    def fake(method, path, body=None, key=True):
        if not key:
            return 401, {}
        if path == "/health":
            return 200, {"status": "ok"}
        if path == "/submit" and body.get("channel") == "fax":
            return 422, {}
        if path == "/submit":
            return 202, {"job_id": "abc1234567", "status": "queued"}
        if path == "/status/abc1234567":
            s = next(states, "needs_review")
            return 200, {"job_id": "abc1234567", "status": s, "text": body_text,
                         "classification": {"product_type": "static_landing_page"} if s == "needs_review" else None}
        return 404, {}

    body_text = "Vorrei una landing page"
    checks, _ = smoke.run_smoke(fake, body_text, wait_seconds=5, poll_seconds=0)
    by_name = {c.name: c for c in checks}
    assert by_name["classified"].ok
    assert "needs_review" in by_name["classified"].detail


def test_wait_fails_on_error_status():
    def fake(method, path, body=None, key=True):
        if not key:
            return 401, {}
        if path == "/health":
            return 200, {"status": "ok"}
        if path == "/submit" and body.get("channel") == "fax":
            return 422, {}
        if path == "/submit":
            return 202, {"job_id": "e000000000", "status": "queued"}
        if path.startswith("/status/e000000000"):
            return 200, {"job_id": "e000000000", "status": "error", "text": "t", "result": "boom"}
        return 404, {}

    checks, _ = smoke.run_smoke(fake, "t", wait_seconds=5, poll_seconds=0)
    classified = {c.name: c for c in checks}["classified"]
    assert not classified.ok
    assert "error" in classified.detail


def test_wait_times_out_when_job_stays_queued():
    def fake(method, path, body=None, key=True):
        if not key:
            return 401, {}
        if path == "/health":
            return 200, {"status": "ok"}
        if path == "/submit" and body.get("channel") == "fax":
            return 422, {}
        if path == "/submit":
            return 202, {"job_id": "q000000000", "status": "queued"}
        if path.startswith("/status/q000000000"):
            return 200, {"job_id": "q000000000", "status": "queued", "text": "t"}
        return 404, {}

    checks, _ = smoke.run_smoke(fake, "t", wait_seconds=0.05, poll_seconds=0.01)
    classified = {c.name: c for c in checks}["classified"]
    assert not classified.ok
    assert "queued" in classified.detail


def test_markdown_summary_lists_every_check():
    checks = [smoke.Check("health", True, "200"), smoke.Check("submit", False, "500")]
    md = smoke.summary_markdown("http://x", checks, "abc")
    assert "health" in md and "submit" in md
    assert "FALLITO" in md
