"""Read changes from Google Calendar with incremental sync (syncToken)."""

from __future__ import annotations

from typing import Any

from googleapiclient.errors import HttpError


def _pages(service: Any, calendar_id: str, **params) -> tuple[list[dict], str | None]:
    items: list[dict] = []
    page_token = None
    while True:
        kw = dict(calendarId=calendar_id, showDeleted=True, maxResults=250, **params)
        if page_token:
            kw["pageToken"] = page_token
        res = service.events().list(**kw).execute()
        items += res.get("items", [])
        page_token = res.get("nextPageToken")
        if not page_token:
            return items, res.get("nextSyncToken")


def fetch_changes(service: Any, calendar_id: str, sync_token: str | None) -> tuple[list[dict], str | None, bool]:
    """Return (items, next_sync_token, was_full_sync).

    With a token only changed events come back. Recurring series are one event (singleEvents is
    off), so a new series is one notification. A stale token (410) triggers a full resync.
    """
    if sync_token:
        try:
            items, nxt = _pages(service, calendar_id, syncToken=sync_token)
            return items, nxt, False
        except HttpError as exc:
            if getattr(exc.resp, "status", None) != 410:
                raise
    items, nxt = _pages(service, calendar_id)
    return items, nxt, True
