"""calendarsentinel: notify when a new event appears on a Google Calendar. Fully offline."""

import json

import pytest
from googleapiclient.errors import HttpError

from calendarsentinel.notify import format_event, send_telegram
from calendarsentinel.sentinel import detect_new, run_once
from calendarsentinel.source import fetch_changes
from calendarsentinel.state import load_state, save_state


def ev(i, status="confirmed", **kw):
    return {"id": f"e{i}", "status": status, "summary": f"Event {i}", **kw}


# ── A1 detection ─────────────────────────────────────────────────────────────

def test_detect_new_returns_only_unknown_confirmed_events():
    new, known = detect_new([ev(1), ev(2)], {"e1"})
    assert [e["id"] for e in new] == ["e2"]
    assert known == {"e1", "e2"}


def test_edit_of_known_event_is_not_new():
    new, _ = detect_new([ev(1, summary="renamed")], {"e1"})
    assert new == []


def test_cancelled_event_is_forgotten_and_not_notified():
    new, known = detect_new([ev(1, status="cancelled")], {"e1"})
    assert new == [] and known == set()


def test_cancelled_unknown_event_is_not_notified():
    new, known = detect_new([ev(9, status="cancelled")], set())
    assert new == [] and known == set()


# ── A2 source ────────────────────────────────────────────────────────────────

class FakeList:
    def __init__(self, pages=None, error=None):
        self.pages, self.error, self.calls = list(pages or []), error, []

    def list(self, **kw):
        self.calls.append(kw)
        return self

    def execute(self):
        if self.error and self.calls[-1].get("syncToken"):
            raise self.error
        return self.pages.pop(0)


class FakeService:
    def __init__(self, lst):
        self.lst = lst

    def events(self):
        return self.lst


def gone():
    resp = type("R", (), {"status": 410, "reason": "Gone"})()
    return HttpError(resp, b"{}")


def test_fetch_follows_pages_and_returns_sync_token():
    lst = FakeList([{"items": [ev(1)], "nextPageToken": "p2"}, {"items": [ev(2)], "nextSyncToken": "S2"}])
    items, token, full = fetch_changes(FakeService(lst), "primary", None)
    assert [e["id"] for e in items] == ["e1", "e2"] and token == "S2" and full is True
    assert lst.calls[1]["pageToken"] == "p2"


def test_fetch_incremental_sends_sync_token_only():
    lst = FakeList([{"items": [], "nextSyncToken": "S3"}])
    items, token, full = fetch_changes(FakeService(lst), "primary", "S2")
    assert lst.calls[0]["syncToken"] == "S2" and "timeMin" not in lst.calls[0]
    assert token == "S3" and full is False


def test_fetch_410_falls_back_to_full_sync():
    lst = FakeList([{"items": [ev(1)], "nextSyncToken": "S9"}], error=gone())
    items, token, full = fetch_changes(FakeService(lst), "primary", "STALE")
    assert token == "S9" and full is True and len(items) == 1


def test_fetch_other_http_error_propagates():
    resp = type("R", (), {"status": 500, "reason": "boom"})()
    lst = FakeList(error=HttpError(resp, b"{}"))
    with pytest.raises(HttpError):
        fetch_changes(FakeService(lst), "primary", "S2")


# ── A3 state ─────────────────────────────────────────────────────────────────

def test_state_roundtrip_and_missing_file(tmp_path):
    p = tmp_path / "s" / "state.json"
    assert load_state(p) == {"sync_token": None, "known": set(), "initialised": False}
    save_state(p, {"sync_token": "T", "known": {"b", "a"}, "initialised": True})
    assert json.loads(p.read_text())["known"] == ["a", "b"]
    assert load_state(p) == {"sync_token": "T", "known": {"a", "b"}, "initialised": True}


# ── A4 notifier ──────────────────────────────────────────────────────────────

def test_format_event_timed_and_all_day():
    t = format_event(ev(1, start={"dateTime": "2026-11-12T15:00:00+01:00"}, location="Bar", htmlLink="http://x"))
    assert "Event 1" in t and "2026-11-12 15:00" in t and "Bar" in t and "http://x" in t
    d = format_event(ev(2, start={"date": "2026-11-13"}))
    assert "2026-11-13" in d and "all day" in d.lower()


def test_format_event_without_title_or_start():
    assert "(no title)" in format_event({"id": "z", "status": "confirmed"})


def test_send_telegram_requires_config(monkeypatch):
    monkeypatch.delenv("TELEGRAM_BOT_TOKEN", raising=False)
    monkeypatch.delenv("NOTIFY_TELEGRAM_CHAT_IDS", raising=False)
    with pytest.raises(RuntimeError):
        send_telegram("hi")


def test_send_telegram_posts_to_each_chat(monkeypatch):
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "TOK")
    monkeypatch.setenv("NOTIFY_TELEGRAM_CHAT_IDS", "1, 2")
    sent = []

    class R:
        status_code = 200

    monkeypatch.setattr("calendarsentinel.notify.httpx.post", lambda url, json, timeout: sent.append((url, json)) or R())
    send_telegram("hi")
    assert [s[1]["chat_id"] for s in sent] == ["1", "2"] and "botTOK" in sent[0][0]


# ── A5 orchestration ─────────────────────────────────────────────────────────

def _svc(*pages):
    return FakeService(FakeList(list(pages)))


def test_first_run_is_a_silent_baseline(tmp_path):
    notified = []
    p = tmp_path / "st.json"
    out = run_once(_svc({"items": [ev(1), ev(2)], "nextSyncToken": "S1"}), p, notified.append)
    assert out == [] and notified == []
    assert load_state(p)["known"] == {"e1", "e2"} and load_state(p)["sync_token"] == "S1"


def test_second_run_notifies_only_the_new_event(tmp_path):
    p = tmp_path / "st.json"
    run_once(_svc({"items": [ev(1)], "nextSyncToken": "S1"}), p, lambda e: None)
    notified = []
    run_once(_svc({"items": [ev(1), ev(2)], "nextSyncToken": "S2"}), p, notified.append)
    assert [e["id"] for e in notified] == ["e2"]
    assert load_state(p)["sync_token"] == "S2"


def test_failed_notification_is_retried_next_run(tmp_path):
    p = tmp_path / "st.json"
    run_once(_svc({"items": [], "nextSyncToken": "S1"}), p, lambda e: None)

    def boom(e):
        raise RuntimeError("telegram down")

    with pytest.raises(RuntimeError):
        run_once(_svc({"items": [ev(5)], "nextSyncToken": "S2"}), p, boom)
    st = load_state(p)
    assert "e5" not in st["known"] and st["sync_token"] == "S1"  # nothing advanced


def test_dry_run_notifies_nobody_and_saves_nothing(tmp_path):
    p = tmp_path / "st.json"
    run_once(_svc({"items": [], "nextSyncToken": "S1"}), p, lambda e: None)
    notified = []
    out = run_once(_svc({"items": [ev(7)], "nextSyncToken": "S2"}), p, notified.append, dry_run=True)
    assert [e["id"] for e in out] == ["e7"] and notified == []
    assert load_state(p)["sync_token"] == "S1"
