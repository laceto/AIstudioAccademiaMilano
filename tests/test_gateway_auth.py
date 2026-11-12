"""tests/test_gateway_auth.py — 047: /submit and /status need X-API-Key; the showcase orders via Telegram."""

import pytest
from fastapi.testclient import TestClient

import gateway.api as api_module
from gateway import middleware
from gateway.auth import api_key_problem
from gateway.pipeline_adapter import PipelineAdapter

KEY = "k" * 40


@pytest.fixture
def client(tmp_path, monkeypatch):
    middleware._buckets.clear()
    monkeypatch.delenv("GATEWAY_ALLOW_OPEN_SUBMIT", raising=False)
    monkeypatch.setenv("GATEWAY_API_KEY", KEY)
    api_module._adapter = PipelineAdapter(queue_dir=str(tmp_path))
    return TestClient(api_module.app)


def _submit(client, headers=None):
    return client.post("/submit", json={"text": "Vorrei una landing page"}, headers=headers or {})


# ── /submit ──────────────────────────────────────────────────────────────────

def test_submit_without_key_is_401(client):
    r = _submit(client)
    assert r.status_code == 401
    assert r.headers.get("www-authenticate") == "ApiKey"


def test_submit_with_wrong_key_is_401(client):
    assert _submit(client, {"X-API-Key": "nope"}).status_code == 401


def test_submit_with_right_key_is_accepted(client):
    r = _submit(client, {"X-API-Key": KEY})
    assert r.status_code == 202 and r.json()["job_id"]


def test_rejected_request_creates_no_job(client):
    _submit(client, {"X-API-Key": "nope"})
    assert api_module._adapter.list_pending() == []


def test_submit_is_closed_when_no_key_is_configured(client, monkeypatch):
    monkeypatch.delenv("GATEWAY_API_KEY")
    r = _submit(client, {"X-API-Key": "anything"})
    assert r.status_code == 503


def test_placeholder_key_counts_as_not_configured(client, monkeypatch):
    monkeypatch.setenv("GATEWAY_API_KEY", "your-gateway-api-key-here")
    assert _submit(client, {"X-API-Key": "your-gateway-api-key-here"}).status_code == 503


def test_short_key_counts_as_not_configured(client, monkeypatch):
    monkeypatch.setenv("GATEWAY_API_KEY", "short")
    assert _submit(client, {"X-API-Key": "short"}).status_code == 503


def test_open_mode_must_be_asked_for_explicitly(client, monkeypatch):
    monkeypatch.delenv("GATEWAY_API_KEY")
    monkeypatch.setenv("GATEWAY_ALLOW_OPEN_SUBMIT", "1")
    assert _submit(client).status_code == 202


def test_open_mode_is_ignored_when_a_key_is_set(client, monkeypatch):
    monkeypatch.setenv("GATEWAY_ALLOW_OPEN_SUBMIT", "1")
    assert _submit(client).status_code == 401


# ── /status ──────────────────────────────────────────────────────────────────

def test_status_without_key_is_401_even_for_a_real_job(client):
    job_id = _submit(client, {"X-API-Key": KEY}).json()["job_id"]
    r = client.get(f"/status/{job_id}")
    assert r.status_code == 401
    assert "Vorrei" not in r.text  # nothing about the job leaks


def test_status_with_key(client):
    job_id = _submit(client, {"X-API-Key": KEY}).json()["job_id"]
    r = client.get(f"/status/{job_id}", headers={"X-API-Key": KEY})
    assert r.status_code == 200 and r.json()["job_id"] == job_id


def test_unknown_job_without_key_is_401_not_404(client):
    # 401 first: an unauthenticated caller must not learn which ids exist
    assert client.get("/status/doesnotexist").status_code == 401


# ── public endpoints stay public ─────────────────────────────────────────────

def test_health_needs_no_key(client):
    assert client.get("/health").status_code == 200


def test_showcase_page_needs_no_key(client):
    assert client.get("/").status_code == 200


# ── showcase: order through Telegram, never /submit from the browser ─────────

def test_showcase_no_longer_calls_submit_or_status(client):
    body = client.get("/").text
    assert 'fetch("/submit"' not in body and "/status/" not in body
    assert "submitIntent" not in body


def test_showcase_links_to_the_telegram_bot(client, monkeypatch):
    monkeypatch.setenv("TELEGRAM_BOT_USERNAME", "@StudioMilanoBot")
    body = client.get("/").text
    assert 'href="https://t.me/StudioMilanoBot"' in body


def test_showcase_without_bot_username_has_no_order_link(client, monkeypatch):
    monkeypatch.delenv("TELEGRAM_BOT_USERNAME", raising=False)
    assert "t.me/" not in client.get("/").text


def test_showcase_ignores_a_malformed_bot_username(client, monkeypatch):
    monkeypatch.setenv("TELEGRAM_BOT_USERNAME", 'bad"><script>x</script>')
    body = client.get("/").text
    assert "t.me/" not in body and "<script>x" not in body


# ── helper ───────────────────────────────────────────────────────────────────

def test_api_key_problem_messages(monkeypatch):
    monkeypatch.delenv("GATEWAY_ALLOW_OPEN_SUBMIT", raising=False)
    monkeypatch.setenv("GATEWAY_API_KEY", KEY)
    assert api_key_problem(KEY) is None
    assert api_key_problem(None) == (401, "Missing or invalid X-API-Key")
    monkeypatch.delenv("GATEWAY_API_KEY")
    code, _ = api_key_problem(KEY)
    assert code == 503
