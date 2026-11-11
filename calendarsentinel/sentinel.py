"""One polling pass: fetch changes, find new events, notify, remember."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Callable

from .source import fetch_changes
from .state import load_state, save_state


def detect_new(items: list[dict], known: set[str]) -> tuple[list[dict], set[str]]:
    """New = event whose id was never seen. Edits are not new; cancellations are forgotten."""
    known = set(known)
    new = []
    for e in items:
        if e.get("status") == "cancelled":
            known.discard(e["id"])
        elif e["id"] not in known:
            new.append(e)
            known.add(e["id"])
    return new, known


def run_once(service: Any, state_path: str | Path, notify: Callable[[dict], None],
             calendar_id: str = "primary", dry_run: bool = False) -> list[dict]:
    """The first run is a silent baseline: what is already on the calendar is not 'new'.

    If a notification fails, events already notified are remembered but the sync token stays
    put, so the next run sees the rest again instead of losing them.
    """
    st = load_state(state_path)
    items, token, _full = fetch_changes(service, calendar_id, st["sync_token"])
    new, known = detect_new(items, st["known"])
    to_send = new if st["initialised"] else []
    if dry_run:
        return to_send
    sent: set[str] = set()
    try:
        for e in to_send:
            notify(e)
            sent.add(e["id"])
    except Exception:
        unsent = {e["id"] for e in to_send} - sent
        save_state(state_path, {**st, "known": known - unsent, "initialised": True})
        raise
    save_state(state_path, {"sync_token": token, "known": known, "initialised": True})
    return to_send
