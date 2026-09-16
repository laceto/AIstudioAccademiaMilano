"""D034 — contract tests for the `deepagents-gcal` package.

The package's own suite lives in
`deliverables/2026-09-16_034_deepagents-gcal/tests/` and runs offline against a
fake Google service. This file guards the repo-level contract: the package
imports, its safety switches hold, and the write tools stay the ones the approval
gate is derived from. LangChain-dependent checks skip when the optional deps are
not installed, so CI stays light.
"""

import sys
from pathlib import Path

import pytest

PACKAGE_SRC = (
    Path(__file__).resolve().parent.parent
    / "deliverables"
    / "2026-09-16_034_deepagents-gcal"
    / "src"
)
sys.path.insert(0, str(PACKAGE_SRC))


def test_package_layout_is_installable():
    root = PACKAGE_SRC.parent
    assert (root / "pyproject.toml").exists()
    assert (root / "README.md").exists()
    assert (root / "LICENSE").exists()
    assert (PACKAGE_SRC / "deepagents_gcal" / "py.typed").exists()


def test_data_layer_imports_without_langchain():
    from deepagents_gcal.config import CalendarSettings
    from deepagents_gcal.models import EventDraft

    settings = CalendarSettings()
    assert settings.calendar_id == "primary"
    assert settings.read_only is False
    assert EventDraft(summary="x", start="2026-09-17T10:00", duration_minutes=30)


def test_read_only_client_refuses_writes():
    from deepagents_gcal.client import GoogleCalendarClient
    from deepagents_gcal.config import CalendarSettings
    from deepagents_gcal.errors import ReadOnlyError
    from deepagents_gcal.models import EventDraft

    client = GoogleCalendarClient(service=object(), settings=CalendarSettings(read_only=True))
    with pytest.raises(ReadOnlyError):
        client.create_event(EventDraft(summary="x", start="2026-09-17T10:00", duration_minutes=30))


def test_allowlist_contains_the_agent_to_named_calendars():
    """calendar_id is only a default; the allowlist is the actual boundary."""
    from deepagents_gcal.client import GoogleCalendarClient
    from deepagents_gcal.config import CalendarSettings
    from deepagents_gcal.errors import CalendarNotAllowedError

    client = GoogleCalendarClient(
        service=object(),
        settings=CalendarSettings(
            calendar_id="agent@studio.it", allowed_calendar_ids=["agent@studio.it"]
        ),
    )
    with pytest.raises(CalendarNotAllowedError):
        client.list_events(calendar_id="primary")


def test_event_text_is_labelled_untrusted_for_the_model():
    pytest.importorskip("langchain_core")
    from deepagents_gcal.prompts import CALENDAR_SYSTEM_PROMPT
    from deepagents_gcal.tools import UNTRUSTED_NOTE

    assert "never instructions" in CALENDAR_SYSTEM_PROMPT.lower()
    assert "not instructions" in UNTRUSTED_NOTE.lower()


def test_settings_describe_redacts_credentials():
    from deepagents_gcal.config import CalendarSettings

    described = CalendarSettings(token_file="/secrets/token.json").describe()
    assert "/secrets/token.json" not in str(described)
    assert described["auth_mode"] == "oauth_user"


def test_scopes_are_least_privilege():
    from deepagents_gcal.auth import SCOPE_EVENTS, SCOPE_READONLY, scopes_for

    assert scopes_for(read_only=True) == [SCOPE_READONLY]
    assert SCOPE_EVENTS in scopes_for(read_only=False)


def test_write_tools_are_the_approval_gated_set():
    pytest.importorskip("langchain_core")
    from deepagents_gcal.tools import WRITE_TOOL_NAMES

    assert set(WRITE_TOOL_NAMES) == {"create_event", "update_event", "delete_event"}


def test_read_only_client_never_builds_write_tools():
    pytest.importorskip("langchain_core")
    from deepagents_gcal.client import GoogleCalendarClient
    from deepagents_gcal.config import CalendarSettings
    from deepagents_gcal.tools import WRITE_TOOL_NAMES, build_calendar_tools

    client = GoogleCalendarClient(service=object(), settings=CalendarSettings(read_only=True))
    names = {t.name for t in build_calendar_tools(client)}
    assert names.isdisjoint(WRITE_TOOL_NAMES)
    assert "find_free_slots" in names


def test_approval_gate_covers_every_write_tool():
    pytest.importorskip("deepagents")
    from deepagents_gcal.agent import build_interrupt_config
    from deepagents_gcal.tools import WRITE_TOOL_NAMES

    config = build_interrupt_config()
    assert set(config) == set(WRITE_TOOL_NAMES)
    assert all("reject" in entry["allowed_decisions"] for entry in config.values())
