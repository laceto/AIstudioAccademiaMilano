"""Runtime settings, read from explicit arguments or the environment.

Nothing here ever holds a secret value: only *paths* to credential files, or the
name of the environment variable that carries the token. Tokens themselves are
loaded in `auth.py`, kept in memory for the process lifetime, and never logged.
"""

from __future__ import annotations

import os
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

ENV_PREFIX = "GCAL_"
DEFAULT_TIMEZONE = "Europe/Rome"
DEFAULT_CALENDAR_ID = "primary"

#: Token JSON can be supplied inline (server deployments without a writable disk).
TOKEN_JSON_ENV = "GCAL_TOKEN_JSON"

_TRUE = {"1", "true", "yes", "on"}
_FALSE = {"0", "false", "no", "off", ""}


def _env_bool(name: str, default: bool) -> bool:
    raw = os.environ.get(name)
    if raw is None:
        return default
    value = raw.strip().lower()
    if value in _TRUE:
        return True
    if value in _FALSE:
        return False
    raise ValueError(f"{name}={raw!r} is not a boolean (use true/false)")


class CalendarSettings(BaseModel):
    """Everything the client and agent need, with safe defaults."""

    model_config = ConfigDict(extra="forbid")

    credentials_file: str = "credentials.json"
    """OAuth *client secrets* file downloaded from Google Cloud Console."""

    token_file: str = "token.json"
    """Where the user's OAuth token is cached. Keep it out of version control."""

    service_account_file: str | None = None
    """Service-account key path; takes precedence over the OAuth flow when set."""

    subject: str | None = None
    """Domain-wide-delegation impersonation target (service accounts only)."""

    calendar_id: str = DEFAULT_CALENDAR_ID
    timezone: str = DEFAULT_TIMEZONE
    read_only: bool = False
    """Request read-only scopes and refuse every write at the client boundary."""

    dry_run: bool = False
    """Validate and echo writes without calling the API — useful in demos and CI."""

    max_results: int = Field(default=25, ge=1, le=250)
    working_hours: tuple[int, int] = (9, 18)
    """Local hours used by `find_free_slots` when no explicit window is given."""

    @classmethod
    def from_env(cls, **overrides: Any) -> "CalendarSettings":
        """Build settings from `GCAL_*` environment variables, then apply overrides."""
        service_account = os.environ.get(f"{ENV_PREFIX}SERVICE_ACCOUNT_FILE") or os.environ.get(
            "GOOGLE_APPLICATION_CREDENTIALS"
        )
        start = int(os.environ.get(f"{ENV_PREFIX}WORK_START", 9))
        end = int(os.environ.get(f"{ENV_PREFIX}WORK_END", 18))
        values: dict[str, Any] = {
            "credentials_file": os.environ.get(f"{ENV_PREFIX}CREDENTIALS_FILE", "credentials.json"),
            "token_file": os.environ.get(f"{ENV_PREFIX}TOKEN_FILE", "token.json"),
            "service_account_file": service_account,
            "subject": os.environ.get(f"{ENV_PREFIX}SUBJECT"),
            "calendar_id": os.environ.get(f"{ENV_PREFIX}CALENDAR_ID", DEFAULT_CALENDAR_ID),
            "timezone": os.environ.get(f"{ENV_PREFIX}TIMEZONE", DEFAULT_TIMEZONE),
            "read_only": _env_bool(f"{ENV_PREFIX}READ_ONLY", False),
            "dry_run": _env_bool(f"{ENV_PREFIX}DRY_RUN", False),
            "max_results": int(os.environ.get(f"{ENV_PREFIX}MAX_RESULTS", 25)),
            "working_hours": (start, end),
        }
        values.update({k: v for k, v in overrides.items() if v is not None})
        return cls(**values)

    def describe(self) -> dict[str, Any]:
        """Redacted view, safe to log or show in a CLI banner."""
        return {
            "calendar_id": self.calendar_id,
            "timezone": self.timezone,
            "read_only": self.read_only,
            "dry_run": self.dry_run,
            "auth_mode": "service_account" if self.service_account_file else "oauth_user",
            "credentials_present": bool(self.service_account_file)
            or os.path.exists(self.credentials_file)
            or bool(os.environ.get(TOKEN_JSON_ENV)),
        }
