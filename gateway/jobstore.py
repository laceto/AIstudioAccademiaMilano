"""Where gateway jobs live.

Jobs used to be JSON files under /tmp/queue. Cloud Run wipes that on every
restart, so a needs_review job could vanish before Luigi saw it, and
GET /status/{job_id} answered 404 for jobs that had existed.

Two backends behind one small contract (put / get / list_by_status):

  FileJobStore       one <job_id>.json per job; local runs and tests
  FirestoreJobStore  one document per job in the `jobs` collection; production

Pick with JOB_STORE=file|firestore (default file). Firestore uses the Cloud Run
service account (needs roles/datastore.user); FIRESTORE_PROJECT and
FIRESTORE_COLLECTION override the defaults (ADC project, "jobs").

Jobs hold what users typed. Set a retention policy (Firestore TTL on a field
such as expire_at) before real traffic: see docs/plans/luigi-approval-notifications.md.
"""

from __future__ import annotations

import json
import os
import re
import threading
from functools import lru_cache
from pathlib import Path
from typing import Protocol

_JOB_ID_RE = re.compile(r"^[A-Za-z0-9_-]{1,64}$")


class JobStore(Protocol):
    def put(self, job: dict) -> None: ...
    def get(self, job_id: str) -> dict | None: ...
    def list_by_status(self, status: str) -> list[dict]: ...
    def transition(self, job_id: str, from_status: str, updates: dict) -> dict | None: ...


def _oldest_first(jobs: list[dict]) -> list[dict]:
    return sorted(jobs, key=lambda j: j.get("created_at", ""))


_file_lock = threading.Lock()  # FileJobStore.transition; the file backend is for local runs


class FileJobStore:
    def __init__(self, queue_dir: str = "gateway/queue"):
        self.queue_dir = Path(queue_dir)
        self.queue_dir.mkdir(parents=True, exist_ok=True)

    def _path(self, job_id: str) -> Path | None:
        # job ids come from URLs (/status/{job_id}): never let one leave queue_dir
        return self.queue_dir / f"{job_id}.json" if _JOB_ID_RE.match(job_id or "") else None

    def put(self, job: dict) -> None:
        path = self._path(job["job_id"])
        if path is None:
            raise ValueError(f"invalid job id: {job['job_id']!r}")
        tmp = path.with_suffix(".json.tmp")
        tmp.write_text(json.dumps(job, indent=2, ensure_ascii=False), encoding="utf-8")
        os.replace(tmp, path)  # readers never see a half-written file

    def get(self, job_id: str) -> dict | None:
        path = self._path(job_id)
        if path is None or not path.exists():
            return None
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            return None

    def list_by_status(self, status: str) -> list[dict]:
        jobs = []
        for f in self.queue_dir.glob("*.json"):
            try:
                job = json.loads(f.read_text(encoding="utf-8"))
            except (json.JSONDecodeError, OSError):
                continue
            if job.get("status") == status:
                jobs.append(job)
        return _oldest_first(jobs)


    def transition(self, job_id: str, from_status: str, updates: dict) -> dict | None:
        """Apply `updates` only if the job is still in `from_status`. Returns the new job, or None.

        This is what makes an approval happen once: of two concurrent decisions, one wins.
        (A lock, so single process; Firestore uses a transaction.)
        """
        with _file_lock:
            job = self.get(job_id)
            if job is None or job.get("status") != from_status:
                return None
            job = {**job, **updates, "job_id": job_id}
            self.put(job)
            return job


def _firestore_client(project: str | None = None):
    try:
        from google.cloud import firestore
    except ImportError as exc:
        raise RuntimeError(
            "JOB_STORE=firestore needs the google-cloud-firestore package (see gateway/requirements.txt)"
        ) from exc
    return firestore.Client(project=project)


class FirestoreJobStore:
    def __init__(self, client=None, collection: str = "jobs", project: str | None = None):
        self._client = client
        self.collection = collection
        self.project = project

    def _collection(self):
        if self._client is None:
            self._client = _firestore_client(self.project)
        return self._client.collection(self.collection)

    def put(self, job: dict) -> None:
        self._collection().document(job["job_id"]).set(job)

    def get(self, job_id: str) -> dict | None:
        if not _JOB_ID_RE.match(job_id or ""):
            return None
        snap = self._collection().document(job_id).get()
        return snap.to_dict() if snap.exists else None

    def list_by_status(self, status: str) -> list[dict]:
        coll = self._collection()
        try:
            from google.cloud.firestore_v1.base_query import FieldFilter

            query = coll.where(filter=FieldFilter("status", "==", status))
        except ImportError:
            query = coll.where("status", "==", status)
        # Filter on one field only: ordering by created_at would need a composite index.
        return _oldest_first([snap.to_dict() for snap in query.stream()])


    def transition(self, job_id: str, from_status: str, updates: dict) -> dict | None:
        """Same contract as FileJobStore.transition, atomic across instances via a transaction."""
        if not _JOB_ID_RE.match(job_id or ""):
            return None
        ref = self._collection().document(job_id)

        @_transactional
        def apply(txn):
            snap = ref.get(transaction=txn)
            if not snap.exists:
                return None
            job = snap.to_dict()
            if job.get("status") != from_status:
                return None
            job = {**job, **updates, "job_id": job_id}
            txn.set(ref, job)
            return job

        return apply(self._client.transaction())


def _transactional(fn):
    """Wrap fn(transaction) in Firestore's retrying transaction decorator (lazy import)."""
    try:
        from google.cloud import firestore
    except ImportError as exc:
        raise RuntimeError(
            "JOB_STORE=firestore needs the google-cloud-firestore package (see gateway/requirements.txt)"
        ) from exc
    return firestore.transactional(fn)


@lru_cache(maxsize=None)
def _cached_firestore_store(project: str | None, collection: str) -> FirestoreJobStore:
    # One Firestore client (gRPC channel) per process, not one per request.
    return FirestoreJobStore(project=project, collection=collection)


def make_store(queue_dir: str = "gateway/queue") -> JobStore:
    """Build the store selected by JOB_STORE (default: file)."""
    backend = os.environ.get("JOB_STORE", "file").strip().lower() or "file"
    if backend == "file":
        return FileJobStore(queue_dir)
    if backend == "firestore":
        return _cached_firestore_store(
            os.environ.get("FIRESTORE_PROJECT") or None,
            os.environ.get("FIRESTORE_COLLECTION", "jobs"),
        )
    raise ValueError(f"Unknown JOB_STORE {backend!r} (expected 'file' or 'firestore')")
