"""scripts/gateway_deliver.py — 048: take a smoke-test job all the way to a deliverable.

The gateway smoke test (046) stops at `needs_review`: in production a job waits there for
Luigi's button. This script plays that part in the GitHub Actions runner, on the runner's
own file job store, never on Firestore:

  1. approves the job with gateway.admin.decide (same checks as the Telegram button);
  2. POSTs {"job_id"} to the real pipeline worker app (gateway/pipeline_worker.py /run),
     in process, so the job goes approved -> running -> awaiting_review | failed;
  3. writes the outcome to --out-dir:
       <deliverable file>   what Chiara produced (only when the run succeeded)
       result.json          status, product type, price, QA, risk, error (no file content)
       steps.txt            the agents' trace

The pipeline calls a real LLM (PIPELINE_PROVIDER, default openai; needs OPENAI_API_KEY or
ANTHROPIC_API_KEY): every run costs money. Telegram stays silent as long as
NOTIFY_TELEGRAM_CHAT_IDS is unset.

Usage (after the smoke test, same GATEWAY_QUEUE_DIR):
  JOB_STORE=file GATEWAY_QUEUE_DIR=... python -m scripts.gateway_deliver \
      --job-id 4dcd51206c --price 0 --out-dir deliverable

Exit code: 0 when the job reached awaiting_review, 1 otherwise.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
from pathlib import Path

ADMIN_ID = "smoke-test-admin"
SUMMARY_FILES = {"result.json", "steps.txt"}
_UNSAFE = re.compile(r"[^A-Za-z0-9._-]+")
_MAX_SUMMARY_CHARS = 20_000


class DeliverError(RuntimeError):
    pass


def safe_filename(name: str | None) -> str:
    """A bare file name that cannot leave out_dir or overwrite the summary files."""
    base = _UNSAFE.sub("_", Path(name or "").name).strip("._")
    if not base:
        return "deliverable.txt"
    if base in SUMMARY_FILES:
        return f"deliverable_{base}"
    return base


def _approve(store, job_id: str, price: float) -> None:
    from gateway.admin import decide

    previous = os.environ.get("ADMIN_TELEGRAM_IDS")
    os.environ["ADMIN_TELEGRAM_IDS"] = ADMIN_ID  # only for this call: decide() checks the admin id
    try:
        decision = decide(store, job_id, ADMIN_ID, "approve", price=price, reason="smoke test")
    finally:
        if previous is None:
            os.environ.pop("ADMIN_TELEGRAM_IDS", None)
        else:
            os.environ["ADMIN_TELEGRAM_IDS"] = previous
    if not decision.ok:
        raise DeliverError(f"approval refused: {decision.code}")


def _run_worker(job_id: str) -> dict:
    from fastapi.testclient import TestClient

    import gateway.pipeline_worker as worker

    r = TestClient(worker.app).post("/run", json={"job_id": job_id})
    if r.status_code != 200:
        raise DeliverError(f"worker /run answered HTTP {r.status_code}")
    return r.json()


def write_outputs(job: dict, out_dir: Path) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)
    result = dict(job.get("result") or {})
    content = result.pop("content", None)
    steps = result.pop("steps", None) or []
    filename = safe_filename(result.get("filename")) if result.get("ok") else None

    if filename and content:
        (out_dir / filename).write_text(content, encoding="utf-8")
    meta = {
        "job_id": job.get("job_id"),
        "status": job.get("status"),
        "price": job.get("price"),
        "filename": filename,
        "error": job.get("error") or result.get("error"),
        **{k: result.get(k) for k in ("product_type", "qa_passed", "risk_score", "high_risk", "skills")},
    }
    (out_dir / "result.json").write_text(json.dumps(meta, indent=2, ensure_ascii=False), encoding="utf-8")
    (out_dir / "steps.txt").write_text("\n\n".join(steps), encoding="utf-8")


def deliver(store, job_id: str, price: float, out_dir: Path) -> dict:
    _approve(store, job_id, price)
    _run_worker(job_id)
    job = store.get(job_id)
    if job is None:
        raise DeliverError("job disappeared after the run")
    write_outputs(job, Path(out_dir))
    return job


def summary_markdown(job: dict) -> str:
    result = job.get("result") or {}
    ok = job.get("status") == "awaiting_review"
    lines = [
        f"## Deliverable — {'pronto' if ok else 'FALLITO'}",
        "",
        "| Campo | Valore |",
        "|---|---|",
        f"| Job | `{job.get('job_id')}` |",
        f"| Stato | `{job.get('status')}` |",
        f"| Prodotto | {result.get('product_type') or '—'} |",
        f"| QA | {'ok' if result.get('qa_passed') else 'no'} |",
        f"| Rischio | {result.get('risk_score', 0):.2f} |",
    ]
    if ok:
        name = safe_filename(result.get("filename"))
        content = result.get("content") or ""
        cut = content[:_MAX_SUMMARY_CHARS]
        lines += [f"| File | `{name}` (artifact `deliverable`) |", "", f"### `{name}`", "", "````", cut, "````"]
        if len(content) > len(cut):
            lines.append(f"_Troncato: il file intero è nell'artifact._")
    else:
        lines += [f"| Errore | {job.get('error') or result.get('error') or '—'} |"]
    return "\n".join(lines) + "\n"


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description="Approva un job di prova e fai girare la pipeline")
    p.add_argument("--job-id", required=True)
    p.add_argument("--price", type=float, default=0.0, help="prezzo approvato (0 = gratis)")
    p.add_argument("--out-dir", default="deliverable")
    a = p.parse_args(argv)

    if os.environ.get("JOB_STORE", "file").strip().lower() != "file":
        print("Solo JOB_STORE=file: questo script non tocca Firestore.", file=sys.stderr)
        return 2

    from gateway.jobstore import make_store

    store = make_store(os.environ.get("GATEWAY_QUEUE_DIR", "gateway/queue"))
    try:
        job = deliver(store, a.job_id, a.price, Path(a.out_dir))
    except DeliverError as exc:
        print(f"[FAIL] {exc}", file=sys.stderr)
        return 1

    print(f"[{'ok' if job.get('status') == 'awaiting_review' else 'FAIL'}] job {a.job_id}: {job.get('status')}")
    for f in sorted(Path(a.out_dir).iterdir()):
        print(f"  {f}")
    summary = os.environ.get("GITHUB_STEP_SUMMARY")
    if summary:
        with open(summary, "a", encoding="utf-8") as fh:
            fh.write(summary_markdown(job))
    return 0 if job.get("status") == "awaiting_review" else 1


if __name__ == "__main__":
    sys.exit(main())
