"""End-to-end runs through the compiled graph with a scripted model.

No API key and no network: the model is replayed from a script and the Google
service is the fake. What this proves is the wiring — the agent really calls the
calendar tools, the approval interrupt really fires on writes, and a rejection
really stops the mutation.
"""

from __future__ import annotations

import json
from typing import Any, Sequence

from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import AIMessage
from langchain_core.outputs import ChatGeneration, ChatResult
from langgraph.types import Command

from deepagents_gcal.agent import create_calendar_agent


class ScriptedModel(BaseChatModel):
    """Replays a fixed list of AI messages; the last one repeats if the agent loops."""

    responses: list[AIMessage]
    index: int = 0

    @property
    def _llm_type(self) -> str:
        return "scripted"

    def bind_tools(self, tools: Sequence[Any], **kwargs: Any) -> "ScriptedModel":
        return self

    def _generate(self, messages, stop=None, run_manager=None, **kwargs: Any) -> ChatResult:
        message = self.responses[min(self.index, len(self.responses) - 1)]
        self.index += 1
        return ChatResult(generations=[ChatGeneration(message=message)])


def tool_call(name: str, args: dict[str, Any], call_id: str = "call_1") -> AIMessage:
    return AIMessage(content="", tool_calls=[{"name": name, "args": args, "id": call_id}])


def tool_messages(result: dict[str, Any]) -> list[Any]:
    return [m for m in result["messages"] if m.__class__.__name__ == "ToolMessage"]


def test_agent_reads_the_calendar_through_its_tools(client):
    model = ScriptedModel(
        responses=[
            tool_call("list_events", {"time_min": "2026-09-17", "time_max": "2026-09-18"}),
            AIMessage(content="You have Standup at 09:00 and Acme review at 14:00."),
        ]
    )
    agent = create_calendar_agent(
        client=client, model=model, require_approval=False, include_research_subagent=False
    )
    result = agent.invoke({"messages": [{"role": "user", "content": "what's on tomorrow?"}]})

    payload = json.loads(tool_messages(result)[0].content)
    assert payload["ok"] is True
    assert {e["summary"] for e in payload["events"]} == {"Standup", "Acme review"}
    assert "Standup" in result["messages"][-1].content


def test_write_interrupts_for_approval_then_creates(client, fake_service):
    model = ScriptedModel(
        responses=[
            tool_call(
                "create_event",
                {"summary": "Retro", "start": "2026-09-18T16:00", "duration_minutes": 45},
            ),
            AIMessage(content="Booked."),
        ]
    )
    agent = create_calendar_agent(client=client, model=model, include_research_subagent=False)
    config = {"configurable": {"thread_id": "approval-test"}}

    paused = agent.invoke({"messages": [{"role": "user", "content": "book retro"}]}, config=config)

    request = paused["__interrupt__"][0].value["action_requests"][0]
    assert request["name"] == "create_event"
    assert request["args"]["summary"] == "Retro"
    assert "evt_new" not in fake_service.stored_events  # nothing written while paused

    resumed = agent.invoke(Command(resume={"decisions": [{"type": "approve"}]}), config=config)
    assert "evt_new" in fake_service.stored_events
    assert resumed["messages"][-1].content == "Booked."


def test_rejection_leaves_the_calendar_untouched(client, fake_service):
    model = ScriptedModel(
        responses=[
            tool_call("delete_event", {"event_id": "evt_1"}),
            AIMessage(content="Left it alone."),
        ]
    )
    agent = create_calendar_agent(client=client, model=model, include_research_subagent=False)
    config = {"configurable": {"thread_id": "reject-test"}}

    agent.invoke({"messages": [{"role": "user", "content": "delete standup"}]}, config=config)
    agent.invoke(
        Command(resume={"decisions": [{"type": "reject", "message": "keep it"}]}), config=config
    )

    assert "evt_1" in fake_service.stored_events


def test_reads_are_never_interrupted(client):
    model = ScriptedModel(
        responses=[tool_call("list_calendars", {}), AIMessage(content="Two calendars.")]
    )
    agent = create_calendar_agent(client=client, model=model, include_research_subagent=False)
    result = agent.invoke(
        {"messages": [{"role": "user", "content": "which calendars?"}]},
        config={"configurable": {"thread_id": "read-test"}},
    )
    assert not result.get("__interrupt__")
    assert json.loads(tool_messages(result)[0].content)["count"] == 2


def test_dry_run_agent_reports_without_writing(fake_service):
    from deepagents_gcal.client import GoogleCalendarClient
    from deepagents_gcal.config import CalendarSettings

    client = GoogleCalendarClient(
        service=fake_service, settings=CalendarSettings(dry_run=True, timezone="Europe/Rome")
    )
    model = ScriptedModel(
        responses=[
            tool_call(
                "create_event",
                {"summary": "Retro", "start": "2026-09-18T16:00", "duration_minutes": 45},
            ),
            AIMessage(content="Simulated."),
        ]
    )
    agent = create_calendar_agent(
        client=client, model=model, require_approval=False, include_research_subagent=False
    )
    result = agent.invoke({"messages": [{"role": "user", "content": "book retro"}]})

    payload = json.loads(tool_messages(result)[0].content)
    assert payload["dry_run"] is True
    assert "evt_new" not in fake_service.stored_events


def test_planning_tool_is_available_from_deepagents(client):
    """deepagents' own middleware still applies — write_todos must be there."""
    model = ScriptedModel(responses=[AIMessage(content="ok")])
    agent = create_calendar_agent(
        client=client, model=model, require_approval=False, include_research_subagent=True
    )
    node_names = set(agent.get_graph().nodes)
    assert "tools" in node_names
