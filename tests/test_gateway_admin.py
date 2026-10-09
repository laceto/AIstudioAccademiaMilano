"""Tests for gateway/admin.py — Luigi's decisions on needs_review jobs.

Only Luigi's numeric Telegram id may decide, a job is decided once, and the price he
sets must be a sane number. The Telegram plumbing is tested separately.
"""

import pytest

from gateway import admin
from gateway.jobstore import FileJobStore

LUIGI = 5670736210


@pytest.fixture(autouse=True)
def _env(monkeypatch):
    monkeypatch.delenv("ADMIN_TELEGRAM_IDS", raising=False)
    monkeypatch.setenv("NOTIFY_TELEGRAM_CHAT_IDS", str(LUIGI))


@pytest.fixture
def store(tmp_path):
    s = FileJobStore(str(tmp_path))
    s.put(
        {
            "job_id": "abc123",
            "status": "needs_review",
            "channel": "telegram",
            "text": "Vorrei un'app per prenotare",
            "metadata": {"chat_id": "190776580"},
            "created_at": "2026-10-09T10:00:00+00:00",
            "classification": {"product_type": "chatbot_app", "confidence": 0.5, "summary": "x"},
        }
    )
    return s


# ── who is an admin ──────────────────────────────────────────────────────────


def test_admin_ids_fall_back_to_the_notification_ids():
    assert admin.admin_ids() == [str(LUIGI)]
    assert admin.is_admin(LUIGI) and admin.is_admin(str(LUIGI))


def test_admin_ids_env_overrides(monkeypatch):
    monkeypatch.setenv("ADMIN_TELEGRAM_IDS", "1, 2")
    assert admin.admin_ids() == ["1", "2"]
    assert not admin.is_admin(LUIGI)


@pytest.mark.parametrize("who", [190776580, "190776580", None, "", "acetoluigi", "@acetoluigi"])
def test_nobody_else_is_admin(who):
    assert not admin.is_admin(who)


def test_no_admin_configured_means_nobody(monkeypatch):
    monkeypatch.delenv("NOTIFY_TELEGRAM_CHAT_IDS")
    assert admin.admin_ids() == [] and not admin.is_admin(LUIGI)


# ── parse_price ──────────────────────────────────────────────────────────────


@pytest.mark.parametrize(
    "raw,expected",
    [
        ("12.5", 12.5),
        ("12,50", 12.5),
        (" EUR 9,90 ", 9.9),
        ("€14.90", 14.9),
        ("0", 0.0),
        ("gratis", 0.0),
        ("Free", 0.0),
        ("100", 100.0),
        ("9.999", 10.0),
    ],
)
def test_parse_price_accepts(raw, expected):
    assert admin.parse_price(raw) == expected


@pytest.mark.parametrize("raw", ["", "abc", "-5", "nan", "inf", "1e9", "20000", "12.5.3", None, "5 euro e 3"])
def test_parse_price_rejects(raw):
    assert admin.parse_price(raw) is None


# ── callback data and keyboard ───────────────────────────────────────────────


@pytest.mark.parametrize("action", ["approve", "reject", "free", "price"])
def test_callback_data_roundtrip(action):
    data = admin.encode_callback(action, "abc123")
    assert len(data.encode()) <= 64  # Telegram's limit
    assert admin.decode_callback(data) == (action, "abc123")


@pytest.mark.parametrize("bad", ["", "zz:abc123", "ap:", "ap:../../x", "ap:abc 123", "approve", None, "ap:" + "a" * 80])
def test_decode_callback_rejects_garbage(bad):
    assert admin.decode_callback(bad) is None


def test_keyboard_offers_the_proposed_price_when_there_is_one():
    kb = admin.review_keyboard("abc123", 9.9)
    texts = [b["text"] for row in kb for b in row]
    assert any("9.90" in t for t in texts)
    assert {admin.decode_callback(b["callback_data"])[0] for row in kb for b in row} == {
        "approve", "reject", "free", "price"
    }


def test_keyboard_has_no_approve_button_without_a_price():
    kb = admin.review_keyboard("abc123", None)
    actions = {admin.decode_callback(b["callback_data"])[0] for row in kb for b in row}
    assert "approve" not in actions and {"reject", "free", "price"} <= actions


def test_proposed_price_comes_from_the_catalogue(store):
    assert admin.proposed_price(store.get("abc123")) == 19.9  # chatbot_app
    assert admin.proposed_price({"classification": {"product_type": "unknown_product"}}) is None
    assert admin.proposed_price({}) is None


# ── decide ───────────────────────────────────────────────────────────────────


def test_approve_sets_status_price_and_who(store):
    d = admin.decide(store, "abc123", LUIGI, "approve", price=14.9)
    assert d.ok and d.code == "approved"
    job = store.get("abc123")
    assert job["status"] == "approved" and job["price"] == 14.9
    assert job["decision"]["by"] == str(LUIGI) and job["decision"]["action"] == "approve"
    assert job["decision"]["at"]


def test_free_is_an_approval_at_zero(store):
    d = admin.decide(store, "abc123", LUIGI, "approve", price=0.0)
    assert d.ok and store.get("abc123")["price"] == 0.0


def test_reject_records_the_reason(store):
    d = admin.decide(store, "abc123", LUIGI, "reject", reason="richiesta illecita")
    assert d.ok and d.code == "rejected"
    job = store.get("abc123")
    assert job["status"] == "rejected" and job["decision"]["reason"] == "richiesta illecita"


def test_a_stranger_cannot_decide(store):
    d = admin.decide(store, "abc123", 190776580, "approve", price=1.0)
    assert not d.ok and d.code == "forbidden"
    assert store.get("abc123")["status"] == "needs_review"


def test_decision_happens_once(store):
    first = admin.decide(store, "abc123", LUIGI, "approve", price=9.9)
    second = admin.decide(store, "abc123", LUIGI, "reject")
    assert first.ok and not second.ok and second.code == "already_decided"
    assert second.job["status"] == "approved"
    assert store.get("abc123")["price"] == 9.9


def test_unknown_job(store):
    assert admin.decide(store, "ghost", LUIGI, "approve", price=1).code == "not_found"


def test_only_needs_review_jobs_can_be_decided(store):
    store.transition("abc123", "needs_review", {"status": "classified"})
    assert admin.decide(store, "abc123", LUIGI, "approve", price=1).code == "not_pending"


@pytest.mark.parametrize("price", [None, -1, float("nan"), float("inf"), 10**6])
def test_approve_needs_a_sane_price(store, price):
    d = admin.decide(store, "abc123", LUIGI, "approve", price=price)
    assert not d.ok and d.code == "bad_price"
    assert store.get("abc123")["status"] == "needs_review"


def test_unknown_action(store):
    assert admin.decide(store, "abc123", LUIGI, "delete").code == "bad_action"


# ── messages ─────────────────────────────────────────────────────────────────


def test_user_message_for_a_paid_approval(store):
    admin.decide(store, "abc123", LUIGI, "approve", price=14.9)
    msg = admin.user_message(store.get("abc123"))
    assert "approvata" in msg.lower() and "14.90" in msg and "abc123" in msg


def test_user_message_for_a_free_approval(store):
    admin.decide(store, "abc123", LUIGI, "approve", price=0.0)
    assert "gratuit" in admin.user_message(store.get("abc123")).lower()


def test_user_message_for_a_rejection_keeps_the_internal_reason_private(store):
    admin.decide(store, "abc123", LUIGI, "reject", reason="sospetto di frode")
    msg = admin.user_message(store.get("abc123"))
    assert "non" in msg.lower() and "abc123" in msg
    assert "frode" not in msg


def test_pending_listing_is_oldest_first_and_bounded(store):
    for i in range(30):
        store.put({"job_id": f"j{i:02d}", "status": "needs_review", "text": f"t{i}",
                   "created_at": f"2026-10-09T11:{i:02d}:00+00:00", "classification": {}})
    jobs = admin.pending_jobs(store, limit=10)
    assert len(jobs) == 10 and jobs[0]["job_id"] == "abc123"
