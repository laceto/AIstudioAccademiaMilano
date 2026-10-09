"""Tests for gateway/notify.py — tell Luigi when a job needs review.

A needs_review job used to sit in /tmp/queue with nobody told. These tests pin
the contract: Telegram + email, configured by env lists, each channel isolated,
no duplicates, no flooding, and no secrets in the logs.
"""

import asyncio
import logging

import pytest

from gateway import notify


@pytest.fixture(autouse=True)
def _clean(monkeypatch):
    for var in (
        "NOTIFY_EMAILS", "NOTIFY_TELEGRAM_CHAT_IDS", "TELEGRAM_BOT_TOKEN",
        "SMTP_HOST", "SMTP_PORT", "SMTP_USER", "SMTP_PASSWORD", "NOTIFY_FROM",
    ):
        monkeypatch.delenv(var, raising=False)
    notify._reset_state()


def _job(job_id="7dff0dd502", text="Mi serve una cosa strana", **over):
    job = {
        "job_id": job_id,
        "channel": "telegram",
        "text": text,
        "metadata": {"chat_id": 190776580, "user_id": 5},
        "classification": {
            "product_type": "unknown_product",
            "confidence": 0.4,
            "summary": "User needs something unusual.",
        },
    }
    job.update(over)
    return job


# ── parse_list ───────────────────────────────────────────────────────────────


@pytest.mark.parametrize(
    "raw,expected",
    [
        (None, []),
        ("", []),
        ("  ", []),
        ("a@x.it", ["a@x.it"]),
        ("a@x.it, b@y.it ,,c@z.it", ["a@x.it", "b@y.it", "c@z.it"]),
        ("A@X.it,a@x.it", ["a@x.it"]),
    ],
)
def test_parse_list(raw, expected):
    assert notify.parse_list(raw) == expected


# ── build_message ────────────────────────────────────────────────────────────


def test_message_has_job_id_text_summary_and_price_tbd():
    subject, body = notify.build_message(_job())
    assert "7dff0dd502" in subject
    for needle in ("7dff0dd502", "Mi serve una cosa strana", "User needs something unusual.", "unknown_product"):
        assert needle in body
    assert "da definire" in body.lower()


def test_message_shows_proposed_price_when_known():
    job = _job()
    job["classification"].update(product_type="static_landing_page", confidence=0.6)
    _, body = notify.build_message(job)
    assert "9.90" in body


def test_message_truncates_user_text():
    _, body = notify.build_message(_job(text="x" * 5000))
    assert "x" * 600 not in body
    assert "troncato" in body.lower()


# ── senders ──────────────────────────────────────────────────────────────────


class _FakeSMTP:
    instances = []

    def __init__(self, host, port, timeout=None):
        self.host, self.port, self.sent, self.started, self.login_args = host, port, [], False, None
        _FakeSMTP.instances.append(self)

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False

    def starttls(self, **kw):
        self.started = True

    def login(self, user, password):
        self.login_args = (user, password)

    def send_message(self, msg):
        self.sent.append(msg)


def test_send_email_one_message_per_recipient_without_exposing_others(monkeypatch):
    _FakeSMTP.instances = []
    monkeypatch.setattr(notify.smtplib, "SMTP", _FakeSMTP)
    monkeypatch.setenv("SMTP_USER", "luigi.vinegar@gmail.com")
    monkeypatch.setenv("SMTP_PASSWORD", "app-pass")
    notify._send_email(["a@x.it", "b@y.it"], "subj", "body")
    smtp = _FakeSMTP.instances[0]
    assert (smtp.host, smtp.port) == ("smtp.gmail.com", 587)
    assert smtp.started and smtp.login_args == ("luigi.vinegar@gmail.com", "app-pass")
    assert [m["To"] for m in smtp.sent] == ["a@x.it", "b@y.it"]
    assert all(m["Subject"] == "subj" for m in smtp.sent)


def test_send_email_requires_credentials(monkeypatch):
    monkeypatch.setattr(notify.smtplib, "SMTP", _FakeSMTP)
    with pytest.raises(RuntimeError):
        notify._send_email(["a@x.it"], "s", "b")


def _fake_client(calls, status):
    class _Resp:
        status_code = status

    class _Client:
        def __init__(self, **kw):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *a):
            return False

        async def post(self, url, json=None):
            calls.append((url, json))
            return _Resp()

    return _Client


def test_send_telegram_posts_plain_text_to_each_chat(monkeypatch):
    calls = []
    monkeypatch.setattr(notify.httpx, "AsyncClient", _fake_client(calls, 200))
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "123:tok")
    asyncio.run(notify._send_telegram(["111", "222"], "ciao *non* markdown"))
    assert [c[1]["chat_id"] for c in calls] == ["111", "222"]
    assert all("parse_mode" not in c[1] for c in calls)  # user text must not be interpreted
    assert all(c[0].endswith("/sendMessage") for c in calls)


def test_send_telegram_raises_on_http_error(monkeypatch):
    monkeypatch.setattr(notify.httpx, "AsyncClient", _fake_client([], 403))
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "123:tok")
    with pytest.raises(RuntimeError):
        asyncio.run(notify._send_telegram(["111"], "x"))


def test_send_telegram_attaches_the_buttons(monkeypatch):
    calls = []
    monkeypatch.setattr(notify.httpx, "AsyncClient", _fake_client(calls, 200))
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "123:tok")
    kb = [[{"text": "ok", "callback_data": "ap:x"}]]
    asyncio.run(notify._send_telegram(["111"], "t", buttons=kb))
    assert calls[0][1]["reply_markup"] == {"inline_keyboard": kb}


def test_send_telegram_without_buttons_sends_no_markup(monkeypatch):
    calls = []
    monkeypatch.setattr(notify.httpx, "AsyncClient", _fake_client(calls, 200))
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "123:tok")
    asyncio.run(notify._send_telegram(["111"], "t"))
    assert "reply_markup" not in calls[0][1]


# ── notify_review ────────────────────────────────────────────────────────────


@pytest.fixture
def spies(monkeypatch):
    log = {"tg": [], "mail": []}

    async def tg(chat_ids, text, buttons=None):
        log["tg"].append((chat_ids, text))
        log.setdefault("buttons", []).append(buttons)

    def mail(recipients, subject, body):
        log["mail"].append((recipients, subject, body))

    monkeypatch.setattr(notify, "_send_telegram", tg)
    monkeypatch.setattr(notify, "_send_email", mail)
    monkeypatch.setenv("NOTIFY_EMAILS", "stekkino@hotmail.it, luigi.vinegar@gmail.com")
    monkeypatch.setenv("NOTIFY_TELEGRAM_CHAT_IDS", "5670736210")
    return log


def test_notify_sends_on_both_channels(spies):
    result = asyncio.run(notify.notify_review(_job()))
    assert spies["tg"][0][0] == ["5670736210"]
    assert spies["mail"][0][0] == ["stekkino@hotmail.it", "luigi.vinegar@gmail.com"]
    assert result == {"telegram": "sent", "email": "sent"}


def _actions(buttons):
    from gateway import admin

    return {admin.decode_callback(b["callback_data"]) for row in buttons for b in row}


def test_telegram_notification_carries_the_decision_buttons(spies):
    job = _job()
    job["classification"].update(product_type="static_landing_page", confidence=0.6)
    asyncio.run(notify.notify_review(job))
    assert _actions(spies["buttons"][0]) == {
        ("approve", "7dff0dd502"), ("free", "7dff0dd502"), ("price", "7dff0dd502"), ("reject", "7dff0dd502"),
    }


def test_unknown_product_has_no_approve_at_proposed_price_button(spies):
    asyncio.run(notify.notify_review(_job()))  # unknown_product: no catalogue price
    assert ("approve", "7dff0dd502") not in _actions(spies["buttons"][0])
    assert ("price", "7dff0dd502") in _actions(spies["buttons"][0])


def test_notify_does_nothing_when_not_configured(monkeypatch):
    calls = []
    monkeypatch.setattr(notify, "_send_email", lambda *a: calls.append("mail"))

    async def tg(*a, **kw):
        calls.append("tg")

    monkeypatch.setattr(notify, "_send_telegram", tg)
    assert asyncio.run(notify.notify_review(_job())) == {}
    assert calls == []


def test_failing_channel_does_not_block_the_other(spies, monkeypatch):
    async def boom(chat_ids, text, buttons=None):
        raise RuntimeError("telegram down")

    monkeypatch.setattr(notify, "_send_telegram", boom)
    result = asyncio.run(notify.notify_review(_job()))
    assert result["telegram"] == "failed"
    assert result["email"] == "sent" and spies["mail"]


def test_only_the_configured_channel_runs(spies, monkeypatch):
    monkeypatch.delenv("NOTIFY_EMAILS")
    result = asyncio.run(notify.notify_review(_job()))
    assert result == {"telegram": "sent"} and not spies["mail"]


def test_same_job_is_notified_once(spies):
    asyncio.run(notify.notify_review(_job()))
    second = asyncio.run(notify.notify_review(_job()))
    assert len(spies["tg"]) == 1 and len(spies["mail"]) == 1
    assert second == {"skipped": "duplicate"}


def test_rate_limit_stops_a_flood(spies, monkeypatch):
    monkeypatch.setattr(notify, "MAX_PER_WINDOW", 3)
    for i in range(6):
        asyncio.run(notify.notify_review(_job(job_id=f"job{i}")))
    assert len(spies["tg"]) == 3
    assert asyncio.run(notify.notify_review(_job(job_id="late"))) == {"skipped": "rate_limited"}


# ── secrets and wiring ───────────────────────────────────────────────────────


def test_failure_logs_never_contain_credentials(spies, monkeypatch, caplog):
    async def boom(chat_ids, text, buttons=None):
        raise RuntimeError("POST https://api.telegram.org/bot123:SECRETTOKEN/sendMessage failed")

    def mail_boom(*a):
        raise RuntimeError("auth failed for password hunter2")

    monkeypatch.setattr(notify, "_send_telegram", boom)
    monkeypatch.setattr(notify, "_send_email", mail_boom)
    with caplog.at_level(logging.DEBUG):
        asyncio.run(notify.notify_review(_job()))
    assert "SECRETTOKEN" not in caplog.text and "hunter2" not in caplog.text
    assert "7dff0dd502" in caplog.text  # the failure is still recorded, by job id


def _worker(monkeypatch, tmp_path, product, needs_review):
    from gateway.worker import QueueWorker

    w = QueueWorker(queue_dir=str(tmp_path))

    async def fake_classify(text):
        return {"product_type": product, "confidence": 0.9, "summary": "s", "needs_review": needs_review}

    monkeypatch.setattr(w, "classify", fake_classify)
    return w


def _queued_job(w):
    result = w.adapter.submit(text="qualcosa", channel="telegram", metadata={"chat_id": 1})
    return w.adapter.get_status(result["job_id"])


def test_process_job_notifies_for_needs_review(monkeypatch, tmp_path):
    seen = []

    async def spy(job):
        seen.append(job["job_id"])
        return {}

    monkeypatch.setattr("gateway.worker.notify_review", spy)
    w = _worker(monkeypatch, tmp_path, "unknown_product", True)
    job = _queued_job(w)
    status, _ = asyncio.run(w.process_job(job))
    assert status == "needs_review" and seen == [job["job_id"]]


def test_process_job_does_not_notify_for_classified(monkeypatch, tmp_path):
    seen = []

    async def spy(job):
        seen.append(job["job_id"])
        return {}

    monkeypatch.setattr("gateway.worker.notify_review", spy)
    w = _worker(monkeypatch, tmp_path, "static_landing_page", False)
    asyncio.run(w.process_job(_queued_job(w)))
    assert seen == []


def test_notification_failure_never_breaks_the_user_reply(monkeypatch, tmp_path):
    async def boom(job):
        raise RuntimeError("smtp exploded")

    monkeypatch.setattr("gateway.worker.notify_review", boom)
    w = _worker(monkeypatch, tmp_path, "unknown_product", True)
    status, reply = asyncio.run(w.process_job(_queued_job(w)))
    assert status == "needs_review" and "Luigi" in reply
