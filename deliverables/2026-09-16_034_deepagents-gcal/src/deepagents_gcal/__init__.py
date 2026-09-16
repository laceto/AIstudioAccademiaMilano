"""deepagents-gcal — a LangChain deepagents agent with Google Calendar tools.

Quick start::

    from deepagents_gcal import create_calendar_agent

    agent = create_calendar_agent()
    result = agent.invoke(
        {"messages": [{"role": "user", "content": "What's on my calendar tomorrow?"}]},
        config={"configurable": {"thread_id": "demo"}},
    )
    print(result["messages"][-1].content)

Just want the tools for your own agent::

    from deepagents_gcal import GoogleCalendarClient, build_calendar_tools

    tools = build_calendar_tools(GoogleCalendarClient.from_env(read_only=True))

`agent` and `tools` pull in LangChain; `client`, `models`, `scheduling` and
`timeutils` do not, so the data layer stays importable on its own.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from .client import GoogleCalendarClient
from .config import CalendarSettings
from .errors import (
    ApiError,
    AuthError,
    CalendarError,
    EventNotFoundError,
    ReadOnlyError,
    TimeParseError,
)
from .models import CalendarRef, Event, EventDraft, EventTime, FreeSlot

__version__ = "0.1.0"

if TYPE_CHECKING:  # pragma: no cover - import-time typing only
    from .agent import create_calendar_agent
    from .tools import WRITE_TOOL_NAMES, build_calendar_tools

_LAZY: dict[str, str] = {
    "create_calendar_agent": ".agent",
    "build_calendar_tools": ".tools",
    "WRITE_TOOL_NAMES": ".tools",
    "CALENDAR_SYSTEM_PROMPT": ".prompts",
}


def __getattr__(name: str) -> Any:
    """Import the LangChain-dependent surface only when it is actually used."""
    module_name = _LAZY.get(name)
    if module_name is None:
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
    from importlib import import_module

    return getattr(import_module(module_name, __name__), name)


__all__ = [
    "ApiError",
    "AuthError",
    "CALENDAR_SYSTEM_PROMPT",
    "CalendarError",
    "CalendarRef",
    "CalendarSettings",
    "Event",
    "EventDraft",
    "EventNotFoundError",
    "EventTime",
    "FreeSlot",
    "GoogleCalendarClient",
    "ReadOnlyError",
    "TimeParseError",
    "WRITE_TOOL_NAMES",
    "__version__",
    "build_calendar_tools",
    "create_calendar_agent",
]
