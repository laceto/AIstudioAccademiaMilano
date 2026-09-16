"""CLI argument handling and the approval loop."""

from __future__ import annotations

import json

import pytest

from deepagents_gcal import cli
from deepagents_gcal.config import CalendarSettings


class FakeAgent:
    """Interrupts once, then answers — the shape `_run_turn` has to survive."""

    def __init__(self, interrupt_first: bool = True) -> None:
        self.interrupt_first = interrupt_first
        self.resumed: list = []

    def invoke(self, payload, config=None):
        if self.interrupt_first:
            self.interrupt_first = False
            interrupt = type(
                "Interrupt",
                (),
                {"value": {"action_requests": [{"name": "create_event", "args": {"summary": "Sync"}}]}},
            )()
            return {"__interrupt__": [interrupt], "messages": []}
        self.resumed.append(payload)
        return {"messages": [type("Msg", (), {"content": "done"})()]}


def test_parser_requires_a_subcommand():
    with pytest.raises(SystemExit):
        cli.build_parser().parse_args([])


def test_global_flags_reach_the_settings(monkeypatch):
    monkeypatch.delenv("GCAL_READ_ONLY", raising=False)
    args = cli.build_parser().parse_args(["--read-only", "--dry-run", "--calendar", "team@studio.it", "tools"])
    settings = cli._settings_from_args(args)
    assert settings.read_only is True
    assert settings.dry_run is True
    assert settings.calendar_id == "team@studio.it"


def test_ask_accepts_model_and_thread():
    args = cli.build_parser().parse_args(["ask", "what's next?", "--model", "openai:gpt-5.5", "--thread", "t1"])
    assert (args.prompt, args.model, args.thread) == ("what's next?", "openai:gpt-5.5", "t1")


def test_run_turn_approves_and_resumes(monkeypatch, capsys):
    agent = FakeAgent()
    monkeypatch.setattr("builtins.input", lambda _="": "y")
    answer = cli._run_turn(agent, {"messages": []}, {"configurable": {"thread_id": "t"}})
    assert answer == "done"
    resume = agent.resumed[0]
    assert resume.resume == {"decisions": [{"type": "approve"}]}
    assert "create_event" in capsys.readouterr().out


def test_run_turn_rejects_with_a_reason(monkeypatch):
    agent = FakeAgent()
    answers = iter(["n", "wrong day"])
    monkeypatch.setattr("builtins.input", lambda _="": next(answers))
    cli._run_turn(agent, {"messages": []}, {"configurable": {"thread_id": "t"}})
    assert agent.resumed[0].resume == {"decisions": [{"type": "reject", "message": "wrong day"}]}


def test_unrecognised_answer_is_treated_as_reject(monkeypatch):
    agent = FakeAgent()
    monkeypatch.setattr("builtins.input", lambda _="": "maybe")
    cli._run_turn(agent, {"messages": []}, {"configurable": {"thread_id": "t"}})
    assert agent.resumed[0].resume["decisions"][0]["type"] == "reject"


def test_tools_command_lists_the_toolset(monkeypatch, capsys, fake_service):

    monkeypatch.setattr(
        cli, "_settings_from_args", lambda args: CalendarSettings(timezone="Europe/Rome")
    )
    monkeypatch.setattr(
        "deepagents_gcal.client.GoogleCalendarClient.service",
        property(lambda self: fake_service),
    )
    assert cli._cmd_tools(cli.build_parser().parse_args(["tools"])) == 0
    output = capsys.readouterr().out
    assert "create_event" in output and "list_events" in output


def test_doctor_reports_missing_credentials(monkeypatch, capsys, tmp_path):
    monkeypatch.delenv("GCAL_TOKEN_JSON", raising=False)
    monkeypatch.setattr(
        cli,
        "_settings_from_args",
        lambda args: CalendarSettings(token_file=str(tmp_path / "absent.json")),
    )
    assert cli._cmd_doctor(cli.build_parser().parse_args(["doctor"])) == 1
    output = capsys.readouterr().out
    assert json.loads(output[: output.index("}") + 1])["calendar_id"] == "primary"
