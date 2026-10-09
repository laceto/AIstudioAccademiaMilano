"""gateway/pipeline_worker.py — the private service Cloud Tasks calls to run the pipeline.

Every run costs LLM money, so the contract is strict: only an `approved` job runs, it runs at
most once whatever Cloud Tasks does, and the endpoint always answers 200 so a failed run is
never retried (and paid for) again behind Luigi's back.
"""

import asyncio
import threading
import time

import pytest
from fastapi.testclient import TestClient

from gateway import pipeline_worker as pw
from gateway.jobstore import FileJobStore
from gateway.studio_runner import RunResult


@pytest.fixture
def env(monkeypatch, tmp_path):
    monkeypatch.setenv("JOB_STORE", "file")
    monkeypatch.setenv("GATEWAY_QUEUE_DIR", str(tmp_path))
    monkeypatch.delenv("PIPELINE_PROVIDER", raising=False)
    monkeypatch.delenv("PIPELINE_RUN_TIMEOUT", raising=False)
    return FileJobStore(str(tmp_path))


def _job(job_id="abc123", status="approved", price=5.5):
    return {
        "job_id": job_id, "status": status, "price": price, "text": "Api service to get current age",
        "channel": "telegram", "metadata": {"chat_id": "190776580"}, "created_at": "2026-10-09T10:00:00+00:00",
    }


class Runner:
    """Stand-in for studio_runner.run_job that counts and records its calls."""

    def __init__(self, result=None, delay=0.0, boom=None):
        self.calls, self.result, self.delay, self.boom = [], result, delay, boom

    def __call__(self, job, *, provider="openai"):
        self.calls.append((dict(job), provider))
        if self.delay:
            time.sleep(self.delay)
        if self.boom:
            raise self.boom
        return self.result or RunResult(
            ok=True, filename="age_api.py", content="print('eta')", product_type="unknown_product",
            price=job["price"], invoice_id="INV-1", qa_passed=True, risk_score=1.0, steps=["[Marco] ok"],
        )


@pytest.fixture
def runner(monkeypatch):
    r = Runner()
    monkeypatch.setattr(pw, "run_job", r)
    return r


@pytest.fixture
def sent(monkeypatch):
    log = []

    async def spy(job, result):
        log.append((job, result))
        return {"telegram": "sent"}

    monkeypatch.setattr(pw, "notify_result", spy)
    return log


@pytest.fixture
def client(env, runner, sent):
    return TestClient(pw.app)


def _run(client, job_id="abc123"):
    return client.post("/run", json={"job_id": job_id})


# ── the happy path ───────────────────────────────────────────────────────────


def test_an_approved_job_runs_and_waits_for_review(client, env, runner, sent):
    env.put(_job())
    resp = _run(client)
    assert resp.status_code == 200 and resp.json() == {"status": "awaiting_review"}
    job = env.get("abc123")
    assert job["status"] == "awaiting_review"
    assert job["result"]["filename"] == "age_api.py" and job["result"]["content"] == "print('eta')"
    assert job["started_at"] and job["finished_at"]
    assert len(runner.calls) == 1 and runner.calls[0][0]["price"] == 5.5


def test_luigi_is_sent_the_result(client, env, sent):
    env.put(_job())
    _run(client)
    assert len(sent) == 1
    job, result = sent[0]
    assert job["job_id"] == "abc123" and result["ok"] is True and result["filename"] == "age_api.py"


def test_the_provider_comes_from_the_environment(client, env, runner, monkeypatch):
    env.put(_job())
    _run(client)
    assert runner.calls[0][1] == "openai"
    env.put(_job("def456"))
    monkeypatch.setenv("PIPELINE_PROVIDER", "anthropic")
    _run(client, "def456")
    assert runner.calls[1][1] == "anthropic"


# ── it never runs what it should not, and never twice ────────────────────────


@pytest.mark.parametrize("status", ["needs_review", "queued", "classified", "rejected", "running",
                                    "awaiting_review", "delivered", "discarded", "failed"])
def test_only_an_approved_job_runs(client, env, runner, sent, status):
    env.put(_job(status=status))
    resp = _run(client)
    assert resp.status_code == 200 and resp.json() == {"skipped": status}
    assert runner.calls == [] and sent == []  # no LLM money, no message
    assert env.get("abc123")["status"] == status


def test_an_unknown_job_is_skipped_with_200(client, runner):
    resp = _run(client, "ghost")
    assert resp.status_code == 200 and resp.json() == {"skipped": "not_found"} and runner.calls == []


def test_a_second_delivery_of_the_same_task_does_not_rerun(client, env, runner):
    env.put(_job())
    _run(client)
    again = _run(client)
    assert again.json() == {"skipped": "awaiting_review"} and len(runner.calls) == 1


def test_concurrent_deliveries_run_the_pipeline_once(env, monkeypatch, sent):
    slow = Runner(delay=0.3)
    monkeypatch.setattr(pw, "run_job", slow)
    env.put(_job())
    answers = []

    def call():
        answers.append(_run(TestClient(pw.app)).json())

    threads = [threading.Thread(target=call) for _ in range(4)]
    [t.start() for t in threads]
    [t.join() for t in threads]
    assert len(slow.calls) == 1
    assert sorted(a.get("status") or "skipped" for a in answers) == ["awaiting_review", "skipped", "skipped", "skipped"]


# ── failures are recorded, reported and never retried ────────────────────────


def test_a_failed_run_is_marked_failed_and_reported(client, env, runner, sent):
    runner.result = RunResult(ok=False, error="QA non superata dopo 3 tentativi")
    env.put(_job())
    resp = _run(client)
    assert resp.status_code == 200 and resp.json() == {"status": "failed"}
    job = env.get("abc123")
    assert job["status"] == "failed" and "QA" in job["error"]
    assert sent[0][1]["ok"] is False


def test_an_exception_in_the_runner_is_a_failed_run_not_a_500(client, env, runner, sent):
    runner.boom = RuntimeError("provider exploded")
    env.put(_job())
    resp = _run(client)
    assert resp.status_code == 200 and resp.json() == {"status": "failed"}
    assert env.get("abc123")["status"] == "failed" and "RuntimeError" in env.get("abc123")["error"]
    assert len(sent) == 1


def test_a_timeout_is_a_failed_run(env, monkeypatch, sent):
    monkeypatch.setenv("PIPELINE_RUN_TIMEOUT", "0.05")
    monkeypatch.setattr(pw, "run_job", Runner(delay=0.5))
    env.put(_job())
    resp = _run(TestClient(pw.app))
    assert resp.json() == {"status": "failed"} and "Timeout" in env.get("abc123")["error"]


def test_a_secret_in_a_runner_error_is_scrubbed_before_it_is_stored(client, env, runner):
    runner.boom = RuntimeError("bad key " + "sk-" + "proj-LEAKME12345")
    env.put(_job())
    _run(client)
    assert "LEAKME" not in env.get("abc123")["error"]


def test_a_failing_notification_does_not_change_the_outcome(client, env, monkeypatch):
    async def broken(job, result):
        raise RuntimeError("telegram down")

    monkeypatch.setattr(pw, "notify_result", broken)
    env.put(_job())
    resp = _run(client)
    assert resp.status_code == 200 and env.get("abc123")["status"] == "awaiting_review"


# ── input validation ─────────────────────────────────────────────────────────


@pytest.mark.parametrize("body", [{}, {"job_id": ""}, {"job_id": "../x"}, {"job_id": "a b"}, {"job_id": "a" * 80}])
def test_bad_requests_are_rejected_without_touching_anything(client, env, runner, body):
    resp = client.post("/run", json=body)
    assert resp.status_code == 422 and runner.calls == []


def test_health(client):
    assert client.get("/health").json() == {"status": "ok"}
