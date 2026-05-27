"""Integration tests for the showcase HTML and JSON endpoints."""

import os

import pytest

os.environ.setdefault("GATEWAY_QUEUE_DIR", "/tmp/queue_test_showcase")

from fastapi.testclient import TestClient  # noqa: E402

from gateway.api import app  # noqa: E402


@pytest.fixture
def client() -> TestClient:
    return TestClient(app)


def test_showcase_json_returns_cards(client: TestClient) -> None:
    r = client.get("/api/showcase")
    assert r.status_code == 200
    body = r.json()
    assert "count" in body and "cards" in body
    assert body["count"] == len(body["cards"])
    assert body["count"] > 0
    for card in body["cards"]:
        for key in ("request_id", "date", "product_type", "price_eur", "title"):
            assert key in card, f"missing {key} in {card}"


def test_showcase_html_renders_gallery(client: TestClient) -> None:
    r = client.get("/")
    assert r.status_code == 200
    assert r.headers["content-type"].startswith("text/html")
    body = r.text
    assert "AI Studio" in body
    assert "€" in body
    assert 'class="card"' in body


def test_health_still_works(client: TestClient) -> None:
    r = client.get("/health")
    assert r.status_code == 200
    assert r.json() == {"status": "ok"}
