"""tests/test_gateway_deliver.py — 048: from a smoke-test job to a downloadable deliverable.

scripts/gateway_deliver.py approves a needs_review job the way Luigi would (gateway.admin.decide),
runs it through the real pipeline worker (/run) and writes what came out to a folder.
The LLM pipeline itself (studio_runner.run_job) is replaced by a fake here.
"""

import json

import pytest

import gateway.pipeline_worker as worker
from gateway.jobstore import make_store
from gateway.pipeline_adapter import PipelineAdapter
from gateway.studio_runner import RunResult
from scripts import gateway_deliver as deliver


@pytest.fixture
def store(tmp_path, monkeypatch):
    q = tmp_path / "queue"
    monkeypatch.setenv("GATEWAY_QUEUE_DIR", str(q))
    monkeypatch.setenv("JOB_STORE", "file")
    monkeypatch.delenv("NOTIFY_TELEGRAM_CHAT_IDS", raising=False)  # no message to Luigi
    monkeypatch.delenv("ADMIN_TELEGRAM_IDS", raising=False)
    return make_store(str(q))


def _job_in_review(store, text="Fai uno script Python che crea una lista"):
    job_id = PipelineAdapter(store=store).submit(text, "api", {"user_id": "smoke"})["job_id"]
    store.transition(job_id, "queued", {"status": "needs_review"})
    return job_id


def _fake_run(ok=True, **kw):
    def run_job(job, provider="openai", version=None):
        run_job.seen = job
        if not ok:
            return RunResult(ok=False, error="boom", steps=["[Stacy] x"])
        return RunResult(ok=True, filename=kw.get("filename", "crea_lista.py"),
                         content="numeri = [1, 2, 3]\nprint(numeri)\n", price=job["price"],
                         product_type="pdf_document", qa_passed=True, steps=["[Stacy] ok", "[Chiara] ok"])
    return run_job


def test_happy_path_writes_the_deliverable(store, tmp_path, monkeypatch):
    monkeypatch.setattr(worker, "run_job", _fake_run())
    job_id = _job_in_review(store)
    out = tmp_path / "out"
    job = deliver.deliver(store, job_id, price=0.0, out_dir=out)

    assert job["status"] == "awaiting_review"
    assert (out / "crea_lista.py").read_text() == "numeri = [1, 2, 3]\nprint(numeri)\n"
    meta = json.loads((out / "result.json").read_text())
    assert meta["status"] == "awaiting_review" and meta["filename"] == "crea_lista.py"
    assert "content" not in meta  # the file holds it; the json is the summary
    assert "Chiara" in (out / "steps.txt").read_text()
    # the pipeline saw the approved price, as with Luigi's button
    assert worker.run_job.seen["price"] == 0.0


def test_failed_run_is_reported_and_writes_no_deliverable(store, tmp_path, monkeypatch):
    monkeypatch.setattr(worker, "run_job", _fake_run(ok=False))
    job_id = _job_in_review(store)
    out = tmp_path / "out"
    job = deliver.deliver(store, job_id, price=0.0, out_dir=out)
    assert job["status"] == "failed"
    meta = json.loads((out / "result.json").read_text())
    assert meta["error"] == "boom"
    assert sorted(p.name for p in out.iterdir()) == ["result.json", "steps.txt"]


def test_job_not_in_review_is_refused(store, tmp_path, monkeypatch):
    monkeypatch.setattr(worker, "run_job", _fake_run())
    job_id = PipelineAdapter(store=store).submit("x", "api", {})["job_id"]  # still queued
    with pytest.raises(deliver.DeliverError, match="not_pending"):
        deliver.deliver(store, job_id, price=0.0, out_dir=tmp_path / "out")


def test_unsafe_filename_is_neutralised(store, tmp_path, monkeypatch):
    monkeypatch.setattr(worker, "run_job", _fake_run(filename="../../etc/passwd"))
    job_id = _job_in_review(store)
    out = tmp_path / "out"
    deliver.deliver(store, job_id, price=0.0, out_dir=out)
    assert (out / "passwd").exists()
    assert not (tmp_path / "etc").exists()


def test_safe_filename_rules():
    assert deliver.safe_filename("crea lista.py") == "crea_lista.py"
    assert deliver.safe_filename("") == "deliverable.txt"
    assert deliver.safe_filename("result.json") == "deliverable_result.json"  # never overwrite the summary
    assert deliver.safe_filename("..") == "deliverable.txt"


def test_summary_markdown_shows_the_file(store, tmp_path, monkeypatch):
    monkeypatch.setattr(worker, "run_job", _fake_run())
    job_id = _job_in_review(store)
    job = deliver.deliver(store, job_id, price=0.0, out_dir=tmp_path / "out")
    md = deliver.summary_markdown(job)
    assert "crea_lista.py" in md and "numeri = [1, 2, 3]" in md and "awaiting_review" in md
