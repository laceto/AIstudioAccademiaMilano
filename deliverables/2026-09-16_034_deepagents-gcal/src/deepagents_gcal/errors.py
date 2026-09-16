"""Exception hierarchy for deepagents-gcal.

Every failure raised by this package is a `CalendarError` subclass, so callers
can catch one type and still tell the cases apart.
"""

from __future__ import annotations


class CalendarError(Exception):
    """Base class for every error raised by this package."""


class AuthError(CalendarError):
    """Credentials are missing, invalid, or insufficient for the requested scope."""


class ReadOnlyError(CalendarError):
    """A write was attempted on a client configured as read-only."""


class EventNotFoundError(CalendarError):
    """The requested event does not exist on the given calendar."""


class ApiError(CalendarError):
    """The Google Calendar API returned an error response."""

    def __init__(self, message: str, *, status: int | None = None) -> None:
        super().__init__(message)
        self.status = status


class TimeParseError(CalendarError):
    """A datetime string could not be interpreted."""
