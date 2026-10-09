"""Hand an approved job to the pipeline worker through Cloud Tasks.

The pipeline run is minutes long and costs LLM calls, and Cloud Run freezes a
container once its request ends, so a Telegram webhook cannot run it. Instead
the gateway creates a Cloud Task that POSTs {"job_id": ...} to the private
`pipeline-worker` service (gateway/pipeline_worker.py), authenticated with an
OIDC token for the pipeline-tasks service account.

Settings (env, all required; without them nothing is queued):
    PIPELINE_QUEUE        queue name, e.g. pipeline-runs
    PIPELINE_WORKER_URL   https URL of the pipeline-worker service
    TASKS_LOCATION        queue region, e.g. europe-west8
    TASKS_INVOKER_SA      service account the task authenticates as (has run.invoker on the worker)
    PIPELINE_PROJECT      optional; defaults to the credentials' project

Duplicates are harmless: the worker claims a job with an atomic status change,
so a second task for the same job is skipped without running the pipeline again.
"""

from __future__ import annotations

import json
import logging
import os
import re
from dataclasses import dataclass

logger = logging.getLogger(__name__)

_JOB_ID_RE = re.compile(r"^[A-Za-z0-9_-]{1,64}$")
DISPATCH_DEADLINE_SECONDS = 900  # matches the worker's Cloud Run request timeout


@dataclass
class EnqueueResult:
    ok: bool
    reason: str  # queued | already_queued | not_configured | bad_job_id | <exception type>


def _config() -> dict | None:
    cfg = {
        "queue": os.environ.get("PIPELINE_QUEUE", "").strip(),
        "worker_url": os.environ.get("PIPELINE_WORKER_URL", "").strip().rstrip("/"),
        "location": os.environ.get("TASKS_LOCATION", "").strip(),
        "invoker": os.environ.get("TASKS_INVOKER_SA", "").strip(),
    }
    return cfg if all(cfg.values()) else None


def _client():
    try:
        from google.cloud import tasks_v2
    except ImportError as exc:
        raise RuntimeError("google-cloud-tasks is not installed (see gateway/requirements.txt)") from exc
    return tasks_v2.CloudTasksClient()


def _default_project() -> str:
    import google.auth

    return google.auth.default()[1]


def enqueue_run(job_id: str) -> EnqueueResult:
    """Create the Cloud Task that runs the pipeline for `job_id`. Never raises."""
    if not isinstance(job_id, str) or not _JOB_ID_RE.match(job_id):
        return EnqueueResult(False, "bad_job_id")
    cfg = _config()
    if cfg is None:
        return EnqueueResult(False, "not_configured")

    try:
        project = os.environ.get("PIPELINE_PROJECT", "").strip() or _default_project()
        parent = f"projects/{project}/locations/{cfg['location']}/queues/{cfg['queue']}"
        task = {
            "http_request": {
                "http_method": "POST",
                "url": f"{cfg['worker_url']}/run",
                "headers": {"Content-Type": "application/json"},
                "body": json.dumps({"job_id": job_id}).encode("utf-8"),
                "oidc_token": {"service_account_email": cfg["invoker"], "audience": cfg["worker_url"]},
            },
            "dispatch_deadline": {"seconds": DISPATCH_DEADLINE_SECONDS},
        }
        _client().create_task(request={"parent": parent, "task": task})
    except Exception as exc:
        if type(exc).__name__ == "AlreadyExists":
            return EnqueueResult(True, "already_queued")
        # type only: provider errors can echo credentials
        logger.warning("[queue] could not enqueue job %s: %s", job_id, type(exc).__name__)
        return EnqueueResult(False, type(exc).__name__)

    logger.info("[queue] job %s queued for the pipeline worker", job_id)
    return EnqueueResult(True, "queued")
