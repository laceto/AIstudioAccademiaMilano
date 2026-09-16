"""Runtime settings, read from explicit arguments or the environment.

Nothing here ever holds a secret value: only *paths* to credential files, or the
name of the environment variable that carries the token. Tokens themselves are
loaded in `auth.py`, kept in memory for the process lifetime, and never logged.
"""

from __future__ import annotations

import os
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, model_validator

from .errors import CalendarError

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
    raise CalendarError(f"{name}={raw!r} is not a boolean (use true/false)")


def _env_int(name: str, default: int) -> int:
    raw = os.environ.get(name)
    if raw is None:
        return default
    try:
        return int(raw)
    except ValueError as exc:
        raise CalendarError(f"{name}={raw!r} is not an integer") from exc


def _env_list(name: str) -> list[str] | None:
    raw = os.environ.get(name)
    if raw is None or not raw.strip():
        return None
    return [item.strip() for item in raw.split(",") if item.strip()]


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
    """Calendar used when a call does not name one."""

    allowed_calendar_ids: list[str] | None = None
    """Hard allowlist. When set, every call naming a calendar outside it is refused.

    Needed because Google's `calendar.events` scope is account-wide: `calendar_id`
    alone is a default, not a boundary, and the agent may pass any id it likes.
    """

    timezone: str = DEFAULT_TIMEZONE
    read_only: bool = False
    """Request read-only scopes and refuse every write at the client boundary."""

    dry_run: bool = False
    """Validate and echo writes without calling the API — useful in demos and CI."""

    max_results: int = Field(default=25, ge=1, le=250)
    max_retries: int = Field(default=2, ge=0, le=5)
    """Retries for transient Google failures (429/5xx), with googleapiclient's backoff."""
    working_hours: tuple[int, int] = (9, 18)
    """Local hours used by `find_free_slots` when no explicit window is given."""

    @model_validator(mode="after")
    def _default_calendar_is_allowed(self) -> "CalendarSettings":
        if self.allowed_calendar_ids and self.calendar_id not in self.allowed_calendar_ids:
            raise ValueError(
                f"calendar_id {self.calendar_id!r} is not in allowed_calendar_ids "
                f"{self.allowed_calendar_ids!r}"
            )
        return self

    @classmethod
    def from_env(cls, **overrides: Any) -> "CalendarSettings":
        """Build settings from `GCAL_*` environment variables, then apply overrides."""
        service_account = os.environ.get(f"{ENV_PREFIX}SERVICE_ACCOUNT_FILE") or os.environ.get(
            "GOOGLE_APPLICATION_CREDENTIALS"
        )
        start = _env_int(f"{ENV_PREFIX}WORK_START", 9)
        end = _env_int(f"{ENV_PREFIX}WORK_END", 18)
        values: dict[str, Any] = {
            "credentials_file": os.environ.get(f"{ENV_PREFIX}CREDENTIALS_FILE", "credentials.json"),
            "token_file": os.environ.get(f"{ENV_PREFIX}TOKEN_FILE", "token.json"),
            "service_account_file": service_account,
            "subject": os.environ.get(f"{ENV_PREFIX}SUBJECT"),
            "calendar_id": os.environ.get(f"{ENV_PREFIX}CALENDAR_ID", DEFAULT_CALENDAR_ID),
            "allowed_calendar_ids": _env_list(f"{ENV_PREFIX}ALLOWED_CALENDAR_IDS"),
            "timezone": os.environ.get(f"{ENV_PREFIX}TIMEZONE", DEFAULT_TIMEZONE),
            "read_only": _env_bool(f"{ENV_PREFIX}READ_ONLY", False),
            "dry_run": _env_bool(f"{ENV_PREFIX}DRY_RUN", False),
            "max_results": _env_int(f"{ENV_PREFIX}MAX_RESULTS", 25),
            "max_retries": _env_int(f"{ENV_PREFIX}MAX_RETRIES", 2),
            "working_hours": (start, end),
        }
        values.update({k: v for k, v in overrides.items() if v is not None})
        try:
            return cls(**values)
        except ValueError as exc:
            raise CalendarError(f"Invalid calendar settings: {exc}") from exc

    def describe(self) -> dict[str, Any]:
        """Redacted view, safe to log or show in a CLI banner."""
        return {
            "calendar_id": self.calendar_id,
            "allowed_calendar_ids": self.allowed_calendar_ids,
            "timezone": self.timezone,
            "read_only": self.read_only,
            "dry_run": self.dry_run,
            "auth_mode": "service_account" if self.service_account_file else "oauth_user",
            "credentials_present": bool(self.service_account_file)
            or os.path.exists(self.credentials_file)
            or bool(os.environ.get(TOKEN_JSON_ENV)),
        }
