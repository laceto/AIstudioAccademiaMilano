"""gateway/pipeline_queue.py — hand an approved job to the private pipeline worker via Cloud Tasks.

Cloud Run freezes a container once its request ends and Telegram's webhook must answer fast,
so the (minutes long, paid) pipeline run is queued, not run inside the webhook.
"""

import json

import pytest

from gateway import pipeline_queue as pq


class FakeTasks:
    def __init__(self, raises=None):
        self.requests, self.raises = [], raises

    def create_task(self, request):
        if self.raises:
            raise self.raises
        self.requests.append(request)
        return {"name": "projects/p/locations/l/queues/q/tasks/1"}


@pytest.fixture
def cfg(monkeypatch):
    monkeypatch.setenv("PIPELINE_QUEUE", "pipeline-runs")
    monkeypatch.setenv("PIPELINE_WORKER_URL", "https://pipeline-worker-abc-oc.a.run.app")
    monkeypatch.setenv("TASKS_LOCATION", "europe-west8")
    monkeypatch.setenv("TASKS_INVOKER_SA", "pipeline-tasks@proj.iam.gserviceaccount.com")
    monkeypatch.setenv("PIPELINE_PROJECT", "proj")


@pytest.fixture
def tasks(monkeypatch, cfg):
    fake = FakeTasks()
    monkeypatch.setattr(pq, "_client", lambda: fake)
    return fake


@pytest.fixture(autouse=True)
def _no_config(monkeypatch):
    for var in ("PIPELINE_QUEUE", "PIPELINE_WORKER_URL", "TASKS_LOCATION", "TASKS_INVOKER_SA", "PIPELINE_PROJECT"):
        monkeypatch.delenv(var, raising=False)


def test_not_configured_does_nothing(monkeypatch):
    monkeypatch.setattr(pq, "_client", lambda: pytest.fail("no client should be built"))
    res = pq.enqueue_run("abc123")
    assert not res.ok and res.reason == "not_configured"


@pytest.mark.parametrize("missing", ["PIPELINE_QUEUE", "PIPELINE_WORKER_URL", "TASKS_INVOKER_SA", "TASKS_LOCATION"])
def test_every_setting_is_required(monkeypatch, tasks, missing):
    monkeypatch.delenv(missing)
    res = pq.enqueue_run("abc123")
    assert not res.ok and res.reason == "not_configured" and not tasks.requests


def test_the_task_targets_the_private_worker_with_an_oidc_token(tasks):
    res = pq.enqueue_run("abc123")
    assert res.ok and res.reason == "queued"
    req = tasks.requests[0]
    assert req["parent"] == "projects/proj/locations/europe-west8/queues/pipeline-runs"
    http = req["task"]["http_request"]
    assert http["url"] == "https://pipeline-worker-abc-oc.a.run.app/run"
    assert http["http_method"] == "POST"
    assert json.loads(http["body"]) == {"job_id": "abc123"}
    assert http["headers"]["Content-Type"] == "application/json"
    assert http["oidc_token"] == {
        "service_account_email": "pipeline-tasks@proj.iam.gserviceaccount.com",
        "audience": "https://pipeline-worker-abc-oc.a.run.app",
    }
    assert req["task"]["dispatch_deadline"] == {"seconds": 900}


def test_a_trailing_slash_in_the_worker_url_is_harmless(monkeypatch, tasks):
    monkeypatch.setenv("PIPELINE_WORKER_URL", "https://w.run.app/")
    pq.enqueue_run("abc123")
    http = tasks.requests[0]["task"]["http_request"]
    assert http["url"] == "https://w.run.app/run" and http["oidc_token"]["audience"] == "https://w.run.app"


def test_the_project_falls_back_to_the_default_credentials(monkeypatch, tasks):
    monkeypatch.delenv("PIPELINE_PROJECT")
    monkeypatch.setattr(pq, "_default_project", lambda: "adc-proj")
    pq.enqueue_run("abc123")
    assert tasks.requests[0]["parent"].startswith("projects/adc-proj/")


@pytest.mark.parametrize("bad", ["", "../x", "a b", "a" * 80, None])
def test_only_well_formed_job_ids_are_queued(tasks, bad):
    res = pq.enqueue_run(bad)
    assert not res.ok and res.reason == "bad_job_id" and not tasks.requests


def test_a_duplicate_task_counts_as_queued(monkeypatch, cfg):
    class AlreadyExists(Exception):
        pass

    monkeypatch.setattr(pq, "_client", lambda: FakeTasks(raises=AlreadyExists("task exists")))
    res = pq.enqueue_run("abc123")
    assert res.ok and res.reason == "already_queued"


def test_a_cloud_error_is_reported_by_type_only(monkeypatch, cfg):
    class PermissionDenied(Exception):
        pass

    secret = "sk-" + "proj-LEAKME12345"
    monkeypatch.setattr(pq, "_client", lambda: FakeTasks(raises=PermissionDenied(f"403 {secret}")))
    res = pq.enqueue_run("abc123")
    assert not res.ok and res.reason == "PermissionDenied"
    assert "LEAKME" not in repr(res)


def test_a_missing_client_library_is_a_clear_failure(monkeypatch, cfg):
    def boom():
        raise RuntimeError("google-cloud-tasks is not installed")

    monkeypatch.setattr(pq, "_client", boom)
    res = pq.enqueue_run("abc123")
    assert not res.ok and res.reason == "RuntimeError"
