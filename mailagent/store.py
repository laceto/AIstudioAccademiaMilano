"""Where to-dos, calendar proposals and per-account scan state live.

JsonStore(path) keeps three JSON files in a directory (local runs); JsonStore(None) is
in-memory (tests, --dry-run). The method set is the contract: a FirestoreStore with the same
methods is what Cloud Run needs, because its disk is wiped between runs.
"""

from __future__ import annotations

import json
import os
from pathlib import Path

PROCESSED_CAP = 2000  # ledger entries kept per account


class JsonStore:
    def __init__(self, path: str | Path | None):
        self.dir = Path(path) if path else None
        self._mem: dict[str, dict] = {}
        if self.dir:
            self.dir.mkdir(parents=True, exist_ok=True)

    def _load(self, name: str) -> dict:
        if self.dir is None:
            return self._mem.setdefault(name, {})
        f = self.dir / f"{name}.json"
        return json.loads(f.read_text(encoding="utf-8")) if f.exists() else {}

    def _save(self, name: str, data: dict) -> None:
        if self.dir is None:
            self._mem[name] = data
            return
        f = self.dir / f"{name}.json"
        tmp = f.with_suffix(".json.tmp")
        tmp.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
        os.replace(tmp, f)

    # scan state ------------------------------------------------------------
    def get_state(self, account_id: str) -> dict:
        return self._load("state").get(account_id, {"cursor": None, "processed": []})

    def set_state(self, account_id: str, state: dict) -> None:
        state = {**state, "processed": state.get("processed", [])[-PROCESSED_CAP:]}
        data = self._load("state")
        data[account_id] = state
        self._save("state", data)

    # to-dos and proposals --------------------------------------------------
    def _add(self, name: str, rec: dict) -> bool:
        data = self._load(name)
        if rec["id"] in data:
            return False
        data[rec["id"]] = rec
        self._save(name, data)
        return True

    def add_todo(self, rec: dict) -> bool:
        return self._add("todos", rec)

    def add_proposal(self, rec: dict) -> bool:
        return self._add("proposals", rec)

    def list_todos(self, status: str | None = None) -> list[dict]:
        return [r for r in self._load("todos").values() if status in (None, r.get("status"))]

    def list_proposals(self, status: str | None = None) -> list[dict]:
        return [r for r in self._load("proposals").values() if status in (None, r.get("status"))]

    def update_proposal(self, pid: str, updates: dict) -> dict:
        data = self._load("proposals")
        data[pid] = {**data[pid], **updates}
        self._save("proposals", data)
        return data[pid]
