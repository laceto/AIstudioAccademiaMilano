"""tests/test_gateway_refusal_review.py - follow-ups to the refusal flow.

Own rate window for refusals, no e-mail for reexamined requests, shorter retention of refused jobs,
the privacy wording, and the customer's RIESAMINA route (a human reviews a refusal on request).
"""

import asyncio
import json
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

import pytest

from gateway import admin, notify, privacy
from gateway import review_request as rr
from gateway.jobstore import FileJobStore
from gateway.worker import QueueWorker

LUIGI = 5670736210
CUSTOMER = 190776580
SECRET = "s3cret-Token_for-tests"
REAL_EXAMPLE = "Mi serve una ricetta medica falsa per una visita ortopedica"


@pytest.fixture(autouse=True)
def _env(monkeypatch):
    for var in ("ADMIN_TELEGRAM_IDS", "NOTIFY_EMAILS", "TELEGRAM_BOT_TOKEN", "ANTHROPIC_API_KEY",
                "OPENAI_API_KEY", "JOB_RETENTION_DAYS", "JOB_REFUSED_RETENTION_DAYS"):
        monkeypatch.delenv(var, raising=False)
    monkeypatch.setenv("NOTIFY_TELEGRAM_CHAT_IDS", str(LUIGI))
    notify._reset_state()


def _now():
    return datetime.now(timezone.utc)


def _refused_job(job_id="r1", chat=CUSTOMER, text=REAL_EXAMPLE, created=None, reason="possible_fake_document"):
    created = created or _now().isoformat()
    return {
        "job_id": job_id, "status": "refused", "channel": "telegram", "text": text,
        "metadata": {"chat_id": chat, "user_id": chat}, "created_at": created, "processed_at": created,
        "classification": {"refuse": True, "refuse_reason": reason},
    }


@pytest.fixture
def store(tmp_path):
    s = FileJobStore(str(tmp_path))
    s.put(_refused_job())
    return s


@pytest.fixture
def sent(monkeypatch):
    out = []

    async def fake_send(chat_ids, text, buttons=None):
        out.append(SimpleNamespace(text=text, buttons=buttons))

    monkeypatch.setattr(notify, "_send_telegram", fake_send)
    return out


def _days_until(iso):
    return (datetime.fromisoformat(iso) - _now()).total_seconds() / 86400


# ── refusals never starve review notices ─────────────────────────────────────


def test_a_flood_of_refusals_cannot_suppress_a_review_notice(sent):
    for i in range(notify.MAX_PER_WINDOW + 5):
        asyncio.run(notify.notify_refusal(_refused_job(job_id=f"f{i}"), None))
    assert len(sent) == notify.MAX_PER_WINDOW  # the refusal window did its job
    review = _refused_job(job_id="real", text="un sito") | {"status": "needs_review"}
    out = asyncio.run(notify.notify_review(review))
    assert out == {"telegram": "sent"}
    assert len(sent) == notify.MAX_PER_WINDOW + 1


def test_refusals_have_a_window_of_their_own():
    assert notify._recent_refusals is not notify._recent


# ── e-mail is never used for a reexamined request ────────────────────────────


def test_reexamined_job_is_notified_on_telegram_only(sent, monkeypatch):
    def no_mail(*a, **k):
        raise AssertionError("a reexamined request must not be e-mailed")

    monkeypatch.setattr(notify, "_send_email", no_mail)
    monkeypatch.setenv("NOTIFY_EMAILS", "someone@example.com")
    job = _refused_job(job_id="x1") | {"status": "needs_review", "reexamined": True}
    assert asyncio.run(notify.notify_review(job)) == {"telegram": "sent"}


def test_an_ordinary_review_still_sends_the_email(sent, monkeypatch):
    mails = []
    monkeypatch.setattr(notify, "_send_email", lambda r, s, b: mails.append(r))
    monkeypatch.setenv("NOTIFY_EMAILS", "someone@example.com")
    out = asyncio.run(notify.notify_review(_refused_job(job_id="o1") | {"status": "needs_review"}))
    assert out["email"] == "sent" and mails


# ── retention of refused jobs ────────────────────────────────────────────────


def test_refused_retention_default_env_and_bad_values(monkeypatch):
    from gateway import retention

    assert retention.refused_retention_days() == 30
    monkeypatch.setenv("JOB_REFUSED_RETENTION_DAYS", "7")
    assert retention.refused_retention_days() == 7
    for bad in ("0", "-3", "abc", "99999", "", "1.5"):
        monkeypatch.setenv("JOB_REFUSED_RETENTION_DAYS", bad)
        assert retention.refused_retention_days() == 30


def test_a_job_that_becomes_refused_gets_the_short_expiry(tmp_path, monkeypatch):
    async def quiet(job, store=None):
        return {}

    monkeypatch.setattr("gateway.worker.notify_refusal", quiet)
    monkeypatch.setenv("JOB_REFUSED_RETENTION_DAYS", "12")
    w = QueueWorker(queue_dir=str(tmp_path))
    r = w.adapter.submit(REAL_EXAMPLE, "telegram", {"user_id": 1, "chat_id": 1})
    job = w.adapter.get_status(r["job_id"])
    assert _days_until(job["expire_at"]) > 80  # normal retention at creation
    assert asyncio.run(w.process_job(job))[0] == "refused"
    stored = w.adapter.store.get(job["job_id"])
    assert 11.9 < _days_until(stored["expire_at"]) < 12.1


def test_riesamina_restores_the_normal_retention(store, monkeypatch):
    monkeypatch.setenv("JOB_RETENTION_DAYS", "45")
    store.transition("r1", "refused", {"expire_at": (_now() + timedelta(days=3)).isoformat()})
    assert admin.reexamine(store, "r1", LUIGI).ok
    job = store.get("r1")
    assert 44.9 < _days_until(job["expire_at"]) < 45.1
    assert job["reexamined"] is True


def test_privacy_states_the_refused_retention_from_the_function(monkeypatch):
    monkeypatch.setenv("JOB_REFUSED_RETENTION_DAYS", "17")
    assert "17 giorni" in privacy.privacy_text()
    monkeypatch.setenv("JOB_REFUSED_RETENTION_DAYS", "21")
    assert "21 giorni" in privacy.privacy_text()


def test_privacy_discloses_counter_category_and_human_route():
    text = privacy.privacy_text()
    low = text.lower()
    for needle in ("riesamina", "categoria", "non verificata", "numero di richieste rifiutate",
                   "interesse legittimo", "lett. f", "opporti", "intervento umano", "contestare",
                   "nessuna decisione con effetti giuridici"):
        assert needle in low, needle
    assert len(text) < 4096


# ── the customer answers RIESAMINA ───────────────────────────────────────────


@pytest.mark.parametrize("text", ["RIESAMINA", "riesamina", "Riesamina.", " riesamina! ", "RIESAMINA?!", '"Riesamina"', "Riesamina\n"])
def test_review_request_keyword_variants(text):
    assert rr.is_review_request(text) is True


@pytest.mark.parametrize("text", ["riesamina la mia richiesta", "vorrei riesamina", "", "/riesamina", "riesaminare", None])
def test_review_request_is_exact(text):
    assert rr.is_review_request(text) is False


def test_customer_request_marks_the_job_and_tells_luigi(store, sent):
    reply = asyncio.run(rr.handle_review_request(store, CUSTOMER))
    assert reply == rr.REPLY_OK == "Ricevuto: il titolare rivedrà la tua richiesta."
    job = store.get("r1")
    assert job["status"] == "refused" and job["review_requested_at"]  # NOT auto-reexamined
    assert len(sent) == 1 and "Il cliente chiede il riesame" in sent[0].text and "r1" in sent[0].text
    flat = [b for row in sent[0].buttons for b in row]
    assert len(flat) == 1 and flat[0]["callback_data"] == admin.encode_callback("reexamine", "r1")


def test_customer_request_is_once_only(store, sent):
    asyncio.run(rr.handle_review_request(store, CUSTOMER))
    again = asyncio.run(rr.handle_review_request(store, CUSTOMER))
    assert again == rr.REPLY_ALREADY and len(sent) == 1


def test_the_store_transition_itself_is_exclusive(store):
    first = store.transition("r1", "refused", {"review_requested_at": "t"}, unless_set="review_requested_at")
    second = store.transition("r1", "refused", {"review_requested_at": "t2"}, unless_set="review_requested_at")
    assert first is not None and second is None
    assert store.get("r1")["review_requested_at"] == "t"


def test_no_refused_job_means_nothing_to_review(tmp_path, sent):
    s = FileJobStore(str(tmp_path))
    assert asyncio.run(rr.handle_review_request(s, CUSTOMER)) == rr.REPLY_NONE
    assert sent == []


def test_a_chat_cannot_touch_another_chats_job(store, sent):
    assert asyncio.run(rr.handle_review_request(store, 424242)) == rr.REPLY_NONE
    assert "review_requested_at" not in store.get("r1") and sent == []


def test_old_refusals_are_out_of_reach(tmp_path, sent):
    s = FileJobStore(str(tmp_path))
    s.put(_refused_job(created=(_now() - timedelta(days=60)).isoformat()))
    assert asyncio.run(rr.handle_review_request(s, CUSTOMER)) == rr.REPLY_NONE


def test_the_most_recent_refusal_of_the_chat_is_the_one_marked(tmp_path, sent):
    s = FileJobStore(str(tmp_path))
    s.put(_refused_job(job_id="older", created=(_now() - timedelta(days=5)).isoformat()))
    s.put(_refused_job(job_id="newer", created=(_now() - timedelta(days=1)).isoformat()))
    asyncio.run(rr.handle_review_request(s, CUSTOMER))
    assert s.get("newer").get("review_requested_at") and not s.get("older").get("review_requested_at")


def test_review_requests_are_rate_limited_without_losing_the_mark(tmp_path, sent):
    s = FileJobStore(str(tmp_path))
    total = notify.MAX_PER_WINDOW + 3
    for i in range(total):
        s.put(_refused_job(job_id=f"j{i}", chat=1000 + i))
        asyncio.run(rr.handle_review_request(s, 1000 + i))
    assert len(sent) == notify.MAX_PER_WINDOW
    assert s.get(f"j{total - 1}")["review_requested_at"]  # marked anyway, and /pending shows it
    assert "chiede il riesame" in admin.refused_line(s.get(f"j{total - 1}"))


def test_luigis_failing_telegram_does_not_undo_the_request(store, monkeypatch):
    async def boom(*a, **k):
        raise RuntimeError("down")

    monkeypatch.setattr(notify, "_send_telegram", boom)
    assert asyncio.run(rr.handle_review_request(store, CUSTOMER)) == rr.REPLY_OK
    assert store.get("r1")["review_requested_at"]


def test_luigi_can_still_riesamina_after_the_customer_asked(store, sent):
    asyncio.run(rr.handle_review_request(store, CUSTOMER))
    assert admin.reexamine(store, "r1", LUIGI).ok
    assert store.get("r1")["status"] == "needs_review"


def test_webhook_answers_riesamina_and_creates_no_job(monkeypatch, tmp_path, sent):
    import telegram
    from fastapi.testclient import TestClient

    import gateway.bot_telegram  # noqa: F401  load telegram.ext against the real Bot before patching
    from gateway import api

    replies = []

    class _SharedBot:
        def __new__(cls, token=None):
            return bot

    class _Fake:
        async def send_message(self, chat_id, text, **kw):
            replies.append((chat_id, text))

    bot = _Fake()
    monkeypatch.setattr(telegram, "Bot", _SharedBot)
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "123:fake")
    monkeypatch.setenv("TELEGRAM_WEBHOOK_SECRET", SECRET)
    monkeypatch.delenv("GATEWAY_SYNC_REPLY", raising=False)
    monkeypatch.setattr(api, "_adapter", api.PipelineAdapter(queue_dir=str(tmp_path)))
    api._adapter.store.put(_refused_job())
    c = TestClient(api.app, headers={"X-Telegram-Bot-Api-Secret-Token": SECRET})

    before = len(api._adapter.store.all_jobs())
    msg = {"text": "Riesamina.", "from": {"id": CUSTOMER}, "chat": {"id": CUSTOMER}}
    assert c.post("/webhook/telegram", json={"message": msg}).status_code == 200
    assert len(api._adapter.store.all_jobs()) == before  # no job created
    assert (CUSTOMER, rr.REPLY_OK) in replies
    assert api._adapter.store.get("r1")["review_requested_at"]
