"""File-backed request queue.

v1 chooses a JSON file for transparency — drop-in replaceable with SQLite or Redis
later. All access is process-local-locked; for multi-process worker concurrency
swap to a real broker.
"""
import json
import time
import uuid
from pathlib import Path
from threading import Lock

QUEUE_PATH = Path(__file__).resolve().parent / "queue.json"
_LOCK = Lock()


def enqueue(request: dict) -> str:
    request_id = uuid.uuid4().hex
    record = {
        "id": request_id,
        "enqueued_at": time.time(),
        "status": "pending",
        **request,
    }
    with _LOCK:
        items = _load()
        items.append(record)
        _save(items)
    return request_id


def get(request_id: str) -> dict | None:
    for item in _load():
        if item["id"] == request_id:
            return item
    return None


def list_all(status: str | None = None) -> list[dict]:
    items = _load()
    if status is None:
        return items
    return [i for i in items if i["status"] == status]


def update_status(request_id: str, status: str, **extra) -> None:
    with _LOCK:
        items = _load()
        for item in items:
            if item["id"] == request_id:
                item["status"] = status
                item.update(extra)
                if status == "done":
                    item["completed_at"] = time.time()
                break
        _save(items)


def _load() -> list[dict]:
    if not QUEUE_PATH.exists():
        return []
    try:
        return json.loads(QUEUE_PATH.read_text())
    except json.JSONDecodeError:
        return []


def _save(items: list[dict]) -> None:
    QUEUE_PATH.write_text(json.dumps(items, indent=2, default=str))
