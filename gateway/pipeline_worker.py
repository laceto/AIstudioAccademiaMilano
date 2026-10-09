"""The private service that runs the studio pipeline for approved jobs.

Cloud Tasks POSTs {"job_id": ...} to /run (gateway/pipeline_queue.py). The service is
deployed without public access: Cloud Run only lets in the pipeline-tasks service account.

Rules, because every run costs LLM money:
  * only a job in status `approved` runs; the claim (approved -> running) is one atomic
    store.transition(), so a duplicate delivery or a double click cannot run it twice;
  * /run always answers 200 once the request is well formed. A failed run is recorded on
    the job and reported to Luigi, never signalled with an error that would make Cloud
    Tasks retry (the queue is also configured with max-attempts=1);
  * the result is not sent to the customer. It is stored on the job (`awaiting_review`)
    and sent to Luigi, who decides (Invia al cliente / Scarta).

Env: JOB_STORE=firestore, PIPELINE_PROVIDER (default openai), PIPELINE_RUN_TIMEOUT seconds
(default 600; the Cloud Run request timeout is 900), TELEGRAM_BOT_TOKEN and
NOTIFY_TELEGRAM_CHAT_IDS for the message to Luigi, OPENAI_API_KEY for the LLM.
"""

from __future__ import annotations

import asyncio
import logging
import os
import re
from datetime import datetime, timezone

from fastapi import FastAPI
from pydantic import BaseModel, field_validator

from gateway.jobstore import make_store
from gateway.notify import notify_result
from gateway.studio_runner import RunResult, run_job, scrub

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")

app = FastAPI(title="AI Studio pipeline worker")

_JOB_ID_RE = re.compile(r"^[A-Za-z0-9_-]{1,64}$")


class RunBody(BaseModel):
    job_id: str

    @field_validator("job_id")
    @classmethod
    def _well_formed(cls, value: str) -> str:
        if not _JOB_ID_RE.match(value):
            raise ValueError("malformed job id")
        return value


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _run_timeout() -> float:
    return float(os.environ.get("PIPELINE_RUN_TIMEOUT", "600"))


@app.get("/health")
async def health():
    return {"status": "ok"}


@app.post("/run")
async def run(body: RunBody):
    store = make_store(os.environ.get("GATEWAY_QUEUE_DIR", "gateway/queue"))

    job = store.transition(body.job_id, "approved", {"status": "running", "started_at": _now()})
    if job is None:
        current = store.get(body.job_id)
        reason = current.get("status", "unknown") if current else "not_found"
        logger.info("[worker] job %s skipped (%s)", body.job_id, reason)
        return {"skipped": reason}

    logger.info("[worker] job %s running", body.job_id)
    try:
        result = await asyncio.wait_for(
            asyncio.to_thread(run_job, job, provider=os.environ.get("PIPELINE_PROVIDER", "openai")),
            timeout=_run_timeout(),
        )
    except asyncio.TimeoutError:
        result = RunResult(ok=False, error=f"Timeout: la pipeline non ha finito entro {int(_run_timeout())} secondi.")
    except Exception as exc:
        result = RunResult(ok=False, error=scrub(f"{type(exc).__name__}: {exc}"))

    status = "awaiting_review" if result.ok else "failed"
    data = result.to_dict()
    finished = store.transition(
        body.job_id, "running",
        {"status": status, "finished_at": _now(), "result": data, "error": result.error},
    )
    if finished is None:
        logger.error("[worker] job %s was no longer 'running' when the run ended", body.job_id)
    logger.info("[worker] job %s -> %s", body.job_id, status)

    try:
        await notify_result(job, data)
    except Exception as exc:  # the outcome is already stored; Luigi can find it with /pending
        logger.warning("[worker] could not notify Luigi about job %s: %s", body.job_id, type(exc).__name__)

    return {"status": status}
