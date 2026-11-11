"""Sentinel state: the Calendar sync token and the ids already seen. One small JSON file."""

from __future__ import annotations

import json
import os
from pathlib import Path


def load_state(path: str | Path) -> dict:
    p = Path(path)
    if not p.exists():
        return {"sync_token": None, "known": set(), "initialised": False}
    d = json.loads(p.read_text(encoding="utf-8"))
    return {"sync_token": d.get("sync_token"), "known": set(d.get("known", [])), "initialised": bool(d.get("initialised"))}


def save_state(path: str | Path, state: dict) -> None:
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    data = {"sync_token": state["sync_token"], "known": sorted(state["known"]), "initialised": state["initialised"]}
    tmp = p.with_suffix(p.suffix + ".tmp")
    tmp.write_text(json.dumps(data, indent=1), encoding="utf-8")
    os.replace(tmp, p)  # atomic: a crash never leaves half a file
