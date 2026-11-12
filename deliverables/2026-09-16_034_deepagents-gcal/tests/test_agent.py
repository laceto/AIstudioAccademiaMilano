"""Agent wiring: toolset, approval gate, subagent, and package surface."""

from __future__ import annotations

import pytest
from langchain_core.language_models.fake_chat_models import GenericFakeChatModel

from deepagents_gcal.agent import (
    build_interrupt_config,
    build_research_subagent,
    create_calendar_agent,
    default_model,
)
from deepagents_gcal.client import GoogleCalendarClient
from deepagents_gcal.config import CalendarSettings
from deepagents_gcal.tools import WRITE_TOOL_NAMES


@pytest.fixture
def model() -> GenericFakeChatModel:
    return GenericFakeChatModel(messages=iter([]))


def test_interrupt_config_covers_exactly_the_write_tools():
    config = build_interrupt_config()
    assert set(config) == set(WRITE_TOOL_NAMES)
    for entry in config.values():
        assert entry["allowed_decisions"] == ["approve", "edit", "reject"]
        assert entry["description"]


def test_research_subagent_is_read_only(client):
    subagent = build_research_subagent(client)
    assert subagent["name"] == "schedule-researcher"
    names = {tool.name for tool in subagent["tools"]}
    assert names.isdisjoint(WRITE_TOOL_NAMES)
    assert "list_events" in names


def test_agent_compiles_with_the_calendar_toolset(client, model):
    agent = create_calendar_agent(client=client, model=model)
    assert hasattr(agent, "invoke")
    assert agent.get_graph() is not None


def test_read_only_agent_needs_no_checkpointer(fake_service, model):
    client = GoogleCalendarClient(service=fake_service, settings=CalendarSettings(read_only=True))
    agent = create_calendar_agent(client=client, model=model)
    assert agent.checkpointer is None


def test_approval_provisions_a_checkpointer(client, model):
    agent = create_calendar_agent(client=client, model=model, require_approval=True)
    assert agent.checkpointer is not None


def test_approval_can_be_switched_off(client, model):
    agent = create_calendar_agent(client=client, model=model, require_approval=False)
    assert agent.checkpointer is None


def test_supplied_checkpointer_is_respected(client, model):
    from langgraph.checkpoint.memory import InMemorySaver

    saver = InMemorySaver()
    agent = create_calendar_agent(client=client, model=model, checkpointer=saver)
    assert agent.checkpointer is saver


def test_extra_tools_are_forwarded(client, model):
    from langchain_core.tools import tool

    @tool
    def weather(city: str) -> str:
        """Return the weather for a city."""
        return "sunny"

    agent = create_calendar_agent(client=client, model=model, tools=[weather])
    assert agent is not None  # compilation with a foreign tool must not raise


def test_client_flags_cannot_be_mixed_with_an_injected_client(client, model):
    with pytest.raises(ValueError):
        create_calendar_agent(client=client, model=model, read_only=True)


def test_default_model_is_env_overridable(monkeypatch):
    monkeypatch.setenv("GCAL_AGENT_MODEL", "openai:gpt-5.5")
    assert default_model() == "openai:gpt-5.5"


def test_package_exposes_its_public_surface_lazily():
    import deepagents_gcal as pkg

    assert pkg.__version__
    assert callable(pkg.create_calendar_agent)
    assert callable(pkg.build_calendar_tools)
    with pytest.raises(AttributeError):
        pkg.does_not_exist
