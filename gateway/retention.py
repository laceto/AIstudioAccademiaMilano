"""How long a job is kept.

A job holds what the customer typed (and the pipeline's answer), so it must not live forever.
This is the single place that says how long: the Firestore TTL deletes a job document that long
after it was created, and the privacy notice tells the customer the same number.

    JOB_RETENTION_DAYS   default 90; anything that is not a whole number from 1 to 3650 is ignored
"""

from __future__ import annotations

import os
from datetime import datetime, timedelta, timezone

DEFAULT_RETENTION_DAYS = 90
_MAX_DAYS = 3650


def retention_days() -> int:
    raw = os.environ.get("JOB_RETENTION_DAYS", "").strip()
    if raw.isdigit() and 1 <= int(raw) <= _MAX_DAYS:
        return int(raw)
    return DEFAULT_RETENTION_DAYS


def expiry_for(created_at: str | None) -> str:
    """ISO-8601 UTC time at which a job created at `created_at` should be deleted.

    A missing or malformed creation time counts as "now": better to keep a job a little long than
    to leave it with no expiry at all.
    """
    created = datetime.now(timezone.utc)
    if created_at:
        try:
            created = datetime.fromisoformat(created_at)
        except ValueError:
            pass
    if created.tzinfo is None:
        created = created.replace(tzinfo=timezone.utc)
    return (created.astimezone(timezone.utc) + timedelta(days=retention_days())).isoformat()
