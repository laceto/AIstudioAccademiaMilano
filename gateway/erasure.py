"""Erase a customer's data on request (Telegram /cancella, Luigi only).

Pure logic, no Telegram: find the jobs of a chat, delete them safely, keep a record.

Rules
  * A job in `running` or `delivering` is never deleted: a worker may be using it. It is refused,
    and Luigi is told to wait or run /sweep. The status is re-read at the moment of deletion, not
    only when the confirmation card was shown.
  * Deleting twice is harmless: a job that is already gone is reported as such.
  * Only an admin can erase (checked here too, not only in the Telegram layer).
  * Every erasure that removed something leaves one record in `erasures` (accountability). The
    record holds time, who, scope, count and the random job ids. NEVER the chat id, the text or
    the result. It has no TTL: that is a decision for Luigi (see docs/cloud-run-setup.md).

What this module cannot reach, and Luigi must do by hand, is listed by `manual_checklist()`.
"""

from __future__ import annotations

import json
import logging
import os
import re
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path

from gateway.admin import is_admin
from gateway.jobstore import _JOB_ID_RE, _firestore_client
from gateway.privacy import LOG_RETENTION_DAYS

logger = logging.getLogger(__name__)

BUSY_STATUSES = ("running", "delivering")
_CHAT_ID_RE = re.compile(r"^-?\d{1,20}$")
MAX_CARD_ROWS = 15


# ── finding jobs ─────────────────────────────────────────────────────────────


def valid_chat_id(chat_id) -> bool:
    return isinstance(chat_id, str) and bool(_CHAT_ID_RE.match(chat_id.strip()))


_CHAT_TARGET_RE = re.compile(r"^(-?\d{1,20})_(\d{1,6})$")


def parse_chat_target(target) -> tuple[str | None, int | None]:
    """"<chat_id>_<count>" from a Conferma button -> (chat_id, count), or (None, None)."""
    match = _CHAT_TARGET_RE.match(target) if isinstance(target, str) else None
    return (match.group(1), int(match.group(2))) if match else (None, None)


def valid_job_id(job_id) -> bool:
    return isinstance(job_id, str) and bool(_JOB_ID_RE.match(job_id))


def jobs_for_chat(store, chat_id) -> list[dict]:
    """Every job whose metadata.chat_id equals chat_id, compared as text (oldest first)."""
    wanted = str(chat_id).strip()
    return [j for j in store.all_jobs() if str((j.get("metadata") or {}).get("chat_id", "")).strip() == wanted]


# ── the erasure ──────────────────────────────────────────────────────────────


@dataclass
class ErasureResult:
    ok: bool  # False only when the caller may not erase at all
    code: str  # done | nothing | forbidden
    deleted: list[str] = field(default_factory=list)
    refused: list[tuple[str, str]] = field(default_factory=list)  # (job_id, status): busy
    missing: list[str] = field(default_factory=list)  # already gone
    failed: list[tuple[str, str]] = field(default_factory=list)  # (job_id, exception TYPE): store error
    expected: int | None = None  # chat scope: the count on the card (code "changed" when it differs)
    found: int | None = None  # chat scope: the count found now


def erase_jobs(store, job_ids: list[str], admin_id) -> ErasureResult:
    """Delete these jobs, except busy ones. The status is read again right before each delete."""
    if not is_admin(admin_id):
        return ErasureResult(False, "forbidden")
    result = ErasureResult(True, "nothing")
    for job_id in job_ids:
        try:
            job = store.get(job_id)
            if job is None:
                result.missing.append(job_id)
            elif job.get("status") in BUSY_STATUSES:
                result.refused.append((job_id, job.get("status")))
            elif store.delete(job_id):
                result.deleted.append(job_id)
            else:
                result.missing.append(job_id)
        except Exception as exc:  # keep going; what was deleted must still be recorded
            result.failed.append((job_id, type(exc).__name__))  # the type only: messages may carry data
    if result.deleted:
        result.code = "done"
    return result


def erase_chat(store, chat_id, admin_id, expected: int | None = None) -> ErasureResult:
    """Erase every job of a chat, looked up now (not when the card was shown).

    With `expected` (the count the card showed): if the chat has a different number of jobs now,
    delete NOTHING and return code "changed", so Luigi confirms exactly what he saw.
    """
    if not is_admin(admin_id):
        return ErasureResult(False, "forbidden")
    ids = [j["job_id"] for j in jobs_for_chat(store, chat_id)]
    if expected is not None and len(ids) != expected:
        return ErasureResult(True, "changed", expected=expected, found=len(ids))
    return erase_jobs(store, ids, admin_id)


# ── the record ───────────────────────────────────────────────────────────────


def build_record(admin_id, scope: str, job_ids: list[str]) -> dict:
    """The accountability record. No chat id, no customer text, no result: ids are random."""
    return {
        "at": datetime.now(timezone.utc).isoformat(),
        "by": str(admin_id).strip(),
        "scope": scope,  # "job" | "chat"
        "count": len(job_ids),
        "job_ids": list(job_ids),
    }


class FileErasureLog:
    def __init__(self, directory: str = "gateway/erasures"):
        self.directory = Path(directory)
        self.directory.mkdir(parents=True, exist_ok=True)

    def add(self, record: dict) -> str:
        record_id = uuid.uuid4().hex
        (self.directory / f"{record_id}.json").write_text(json.dumps(record, indent=2), encoding="utf-8")
        return record_id

    def all(self) -> list[dict]:
        return sorted(
            (json.loads(f.read_text(encoding="utf-8")) for f in self.directory.glob("*.json")),
            key=lambda r: r.get("at", ""),
        )


class FirestoreErasureLog:
    def __init__(self, client=None, collection: str = "erasures", project: str | None = None):
        self._client, self.collection, self.project = client, collection, project

    def _coll(self):
        if self._client is None:
            self._client = _firestore_client(self.project)
        return self._client.collection(self.collection)

    def add(self, record: dict) -> str:
        record_id = uuid.uuid4().hex
        self._coll().document(record_id).set(record)
        return record_id

    def all(self) -> list[dict]:
        return sorted((s.to_dict() for s in self._coll().stream()), key=lambda r: r.get("at", ""))


def make_erasure_log(directory: str | None = None):
    """Same backend as the jobs (JOB_STORE=file|firestore). File dir: ERASURE_DIR or gateway/erasures."""
    backend = os.environ.get("JOB_STORE", "file").strip().lower() or "file"
    if backend == "file":
        return FileErasureLog(directory or os.environ.get("ERASURE_DIR") or "gateway/erasures")
    if backend == "firestore":
        return FirestoreErasureLog(
            collection=os.environ.get("ERASURES_COLLECTION", "erasures"),
            project=os.environ.get("FIRESTORE_PROJECT") or None,
        )
    raise ValueError(f"Unknown JOB_STORE {backend!r} (expected 'file' or 'firestore')")


def record_erasure(log, admin_id, scope: str, result: ErasureResult) -> bool:
    """Write the record and the one application-log line (ids and counts only). False = record failed."""
    for job_id, kind in result.failed:
        logger.error("[erasure] job %s not deleted: %s", job_id, kind)
    if not result.deleted:
        return True
    logger.info("[erasure] scope=%s deleted=%d jobs=%s", scope, len(result.deleted), ",".join(result.deleted))
    try:
        log.add(build_record(admin_id, scope, result.deleted))
        return True
    except Exception as exc:
        logger.error("[erasure] record NOT written (%s) for jobs=%s", type(exc).__name__, ",".join(result.deleted))
        return False


# ── what Luigi reads ─────────────────────────────────────────────────────────


def _day(job: dict) -> str:
    return str(job.get("created_at") or "?")[:10]


def confirmation_card(jobs: list[dict], scope: str) -> str:
    """The text of the confirmation card. Job id, status, date: never what the customer wrote."""
    what = "questo job" if scope == "job" else "questa chat"
    lines = [f"Cancellare {len(jobs)} job di {what}? Non si torna indietro."]
    for job in jobs[:MAX_CARD_ROWS]:
        lines.append(f"- {job.get('job_id', '?')} | {job.get('status', '?')} | creato {_day(job)}")
    if len(jobs) > MAX_CARD_ROWS:
        lines.append(f"... e altri {len(jobs) - MAX_CARD_ROWS}")
    busy = [j for j in jobs if j.get("status") in BUSY_STATUSES]
    if busy:
        lines.append(
            f"Attenzione: {len(busy)} job sono in corso ({'/'.join(sorted({j['status'] for j in busy}))}) e NON verranno "
            "cancellati: aspetta che finiscano o usa /sweep."
        )
    return "\n".join(lines)


def manual_checklist(job_ids: list[str]) -> str:
    """What the code cannot erase. Wording follows process/runbook_privacy_requests.md."""
    shown = ", ".join(job_ids[:5]) + (" ..." if len(job_ids) > 5 else "")
    return (
        "Da fare a mano (io non posso):\n"
        f"1. E-mail: nella tua casella cancella le copie '[AI Studio] Richiesta da rivedere - job <id>' ({shown}), "
        "poi svuota il cestino.\n"
        "2. Telegram: nella tua chat con il bot cancella i messaggi e i file di revisione che riguardano il cliente.\n"
        f"3. Cloud Logging: le righe [conv] con chat=<id> non si cancellano una per una e scadono da sole dopo "
        f"{LOG_RETENTION_DAYS} giorni. Dillo al cliente.\n"
        "Poi rispondi al cliente (runbook, sezione 4)."
    )


MAX_MESSAGE = 4000  # Telegram refuses 4096; keep a margin


def _ids(items, cap: int = MAX_CARD_ROWS) -> str:
    """Comma list of at most `cap` ids (items may be ids or (id, note) pairs), then '... e altri N'."""
    shown = [i if isinstance(i, str) else f"{i[0]} ({i[1]})" for i in items[:cap]]
    more = f" ... e altri {len(items) - cap}" if len(items) > cap else ""
    return ", ".join(shown) + more


def result_message(result: ErasureResult, record_ok: bool = True) -> str:
    """Luigi's report after pressing Conferma. Always under Telegram's limit, however many jobs."""
    if not result.ok:
        return "Non autorizzato."
    if result.code == "changed":
        return (f"I job di questa chat sono cambiati (erano {result.expected}, ora {result.found}): "
                "non ho cancellato nulla. Rilancia /cancella.")
    parts = []
    if result.failed:
        parts.append(f"{len(result.deleted)} cancellati, {len(result.failed)} falliti: {_ids(result.failed)}. "
                     "Ripeti l'operazione (premi di nuovo Conferma o rilancia /cancella).")
    elif result.deleted:
        parts.append(f"Cancellati {len(result.deleted)} job: {_ids(result.deleted)}.")
    if result.failed and result.deleted:
        parts.append(f"Cancellati: {_ids(result.deleted)}.")
    if result.refused:
        parts.append(f"NON cancellati perche' in corso ({len(result.refused)}): {_ids(result.refused)}. "
                     "Aspetta che finiscano o usa /sweep, poi ripeti /cancella.")
    if result.missing and not result.deleted and not result.refused and not result.failed:
        parts.append("Niente da cancellare: i job non esistono piu' (gia' cancellati?).")
    elif result.missing:
        parts.append(f"Gia' spariti ({len(result.missing)}): {_ids(result.missing)}.")
    if not (result.deleted or result.refused or result.missing or result.failed):
        parts.append("Niente da cancellare.")
    if result.deleted and not record_ok:
        parts.append("ATTENZIONE: non sono riuscito a scrivere il registro delle cancellazioni (vedi i log). Annota tu la data.")
    body = "\n".join(parts)
    tail = ("\n" + manual_checklist(result.deleted)) if result.deleted else ""
    room = MAX_MESSAGE - len(tail)
    if len(body) > room:
        body = body[: max(0, room - 3)] + "..."
    return body + tail
