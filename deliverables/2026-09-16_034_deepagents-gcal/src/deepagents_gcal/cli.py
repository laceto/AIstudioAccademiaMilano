"""Command line entry point: `deepagents-gcal`.

Subcommands
-----------
``auth``    run the OAuth consent flow once and cache the token
``doctor``  show the resolved configuration and check credentials load
``tools``   list the tools the agent will be given
``ask``     one-shot question
``chat``    interactive REPL

Both ``ask`` and ``chat`` handle approval interrupts inline: when the agent wants
to write to the calendar, the pending call is printed and you approve or reject it.
"""

from __future__ import annotations

import argparse
import json
import sys
from typing import Any

from .config import CalendarSettings
from .errors import CalendarError

APPROVE = {"y", "yes", "a", "approve", ""}
REJECT = {"n", "no", "r", "reject"}


def _settings_from_args(args: argparse.Namespace) -> CalendarSettings:
    overrides: dict[str, Any] = {}
    if getattr(args, "calendar", None):
        overrides["calendar_id"] = args.calendar
    if getattr(args, "timezone", None):
        overrides["timezone"] = args.timezone
    if getattr(args, "read_only", False):
        overrides["read_only"] = True
    if getattr(args, "dry_run", False):
        overrides["dry_run"] = True
    return CalendarSettings.from_env(**overrides)


def _build_agent(args: argparse.Namespace) -> tuple[Any, Any]:
    from .agent import create_calendar_agent
    from .client import GoogleCalendarClient

    settings = _settings_from_args(args)
    client = GoogleCalendarClient(settings=settings)
    agent = create_calendar_agent(
        client=client,
        model=getattr(args, "model", None),
        require_approval=not getattr(args, "no_approval", False),
        include_research_subagent=not getattr(args, "no_subagent", False),
    )
    return agent, settings


def _print_interrupt(interrupt: Any) -> None:
    value = getattr(interrupt, "value", interrupt)
    requests = (value or {}).get("action_requests", []) if isinstance(value, dict) else []
    for request in requests:
        name = request.get("name") or request.get("action") or "tool call"
        args = request.get("args", {})
        print(f"\n  ⚠  The agent wants to run: {name}")
        print(f"     {json.dumps(args, ensure_ascii=False, indent=6, default=str)}")


def _resume_decisions(interrupt: Any) -> list[dict[str, Any]]:
    """Ask the operator about each pending action and build the resume payload."""
    value = getattr(interrupt, "value", interrupt)
    requests = (value or {}).get("action_requests", []) if isinstance(value, dict) else []
    decisions: list[dict[str, Any]] = []
    for _ in requests or [None]:
        answer = input("     approve? [Y/n] ").strip().lower()
        if answer in REJECT:
            reason = input("     reason (optional): ").strip()
            decision: dict[str, Any] = {"type": "reject"}
            if reason:
                decision["message"] = reason
            decisions.append(decision)
        elif answer in APPROVE:
            decisions.append({"type": "approve"})
        else:
            print("     Unrecognised answer — treating as reject.")
            decisions.append({"type": "reject", "message": "operator did not approve"})
    return decisions


def _run_turn(agent: Any, payload: Any, config: dict[str, Any]) -> str:
    """Invoke the agent, pausing for approval whenever it interrupts."""
    from langgraph.types import Command

    result = agent.invoke(payload, config=config)
    while result.get("__interrupt__"):
        for interrupt in result["__interrupt__"]:
            _print_interrupt(interrupt)
        decisions = _resume_decisions(result["__interrupt__"][0])
        result = agent.invoke(Command(resume={"decisions": decisions}), config=config)

    messages = result.get("messages", [])
    return messages[-1].content if messages else ""


def _cmd_auth(args: argparse.Namespace) -> int:
    from .auth import load_credentials

    settings = _settings_from_args(args)
    load_credentials(settings, allow_interactive=True)
    print(f"✓ Token stored at {settings.token_file} (permissions 0600). Do not commit it.")
    return 0


def _cmd_doctor(args: argparse.Namespace) -> int:
    settings = _settings_from_args(args)
    print(json.dumps(settings.describe(), indent=2))
    try:
        from .auth import load_credentials

        load_credentials(settings)
        print("✓ Credentials load successfully.")
        return 0
    except CalendarError as exc:
        print(f"✗ {exc}")
        return 1


def _cmd_tools(args: argparse.Namespace) -> int:
    from .client import GoogleCalendarClient
    from .tools import build_calendar_tools

    client = GoogleCalendarClient(settings=_settings_from_args(args))
    for tool in build_calendar_tools(client):
        print(f"{tool.name:<18} {tool.description.splitlines()[0]}")
    return 0


def _cmd_ask(args: argparse.Namespace) -> int:
    agent, settings = _build_agent(args)
    config = {"configurable": {"thread_id": args.thread}}
    answer = _run_turn(agent, {"messages": [{"role": "user", "content": args.prompt}]}, config)
    print(answer)
    return 0


def _cmd_chat(args: argparse.Namespace) -> int:
    agent, settings = _build_agent(args)
    config = {"configurable": {"thread_id": args.thread}}
    banner = settings.describe()
    print(f"deepagents-gcal — calendar {banner['calendar_id']} ({banner['timezone']})")
    if banner["read_only"]:
        print("read-only mode: no write tools are loaded")
    if banner["dry_run"]:
        print("dry-run mode: writes are validated but never sent to Google")
    print("Type 'exit' to quit.\n")
    while True:
        try:
            user_input = input("you › ").strip()
        except (EOFError, KeyboardInterrupt):
            print()
            return 0
        if user_input.lower() in {"exit", "quit"}:
            return 0
        if not user_input:
            continue
        answer = _run_turn(agent, {"messages": [{"role": "user", "content": user_input}]}, config)
        print(f"\nagent › {answer}\n")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="deepagents-gcal",
        description="A deepagents agent with Google Calendar tools.",
    )
    parser.add_argument("--calendar", help="Calendar id (default: primary)")
    parser.add_argument("--timezone", help="IANA timezone, e.g. Europe/Rome")
    parser.add_argument("--read-only", action="store_true", help="Load no write tools")
    parser.add_argument("--dry-run", action="store_true", help="Validate writes without sending them")

    sub = parser.add_subparsers(dest="command", required=True)

    sub.add_parser("auth", help="Run the OAuth consent flow and cache the token")
    sub.add_parser("doctor", help="Show resolved configuration and check credentials")
    sub.add_parser("tools", help="List the tools the agent will receive")

    for name, help_text in (("ask", "Ask one question"), ("chat", "Interactive session")):
        cmd = sub.add_parser(name, help=help_text)
        if name == "ask":
            cmd.add_argument("prompt", help="What to ask the agent")
        cmd.add_argument("--model", help="Model id, e.g. anthropic:claude-sonnet-5")
        cmd.add_argument("--thread", default="cli", help="Conversation thread id")
        cmd.add_argument("--no-approval", action="store_true", help="Do not pause before writes")
        cmd.add_argument("--no-subagent", action="store_true", help="Disable the research subagent")

    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    handlers = {
        "auth": _cmd_auth,
        "doctor": _cmd_doctor,
        "tools": _cmd_tools,
        "ask": _cmd_ask,
        "chat": _cmd_chat,
    }
    try:
        return handlers[args.command](args)
    except CalendarError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    except KeyboardInterrupt:  # pragma: no cover - interactive
        return 130


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
