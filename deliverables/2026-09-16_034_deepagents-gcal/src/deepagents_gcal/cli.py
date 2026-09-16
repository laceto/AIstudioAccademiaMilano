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

#: Approval is explicit — a bare Return rejects. These writes are irreversible, and the
#: operator pressing Enter to get past a prompt must not be how a deletion gets approved.
APPROVE = {"y", "yes", "approve"}
REJECT = {"n", "no", "r", "reject", ""}


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


def _action_requests(interrupt: Any) -> list[dict[str, Any]]:
    value = getattr(interrupt, "value", interrupt)
    if not isinstance(value, dict):
        return []
    return list(value.get("action_requests", []))


def _describe(request: dict[str, Any]) -> str:
    name = request.get("name") or request.get("action") or "tool call"
    args = json.dumps(request.get("args", {}), ensure_ascii=False, indent=6, default=str)
    return f"  ⚠  The agent wants to run: {name}\n     {args}"


def _resume_decisions(interrupt: Any) -> list[dict[str, Any]]:
    """Ask the operator about each pending action and build the resume payload.

    One decision per action request, in order, each prompted right after the call it
    refers to — a batched interrupt otherwise invites answering about one call and having
    it applied to another.
    """
    decisions: list[dict[str, Any]] = []
    for request in _action_requests(interrupt) or [{}]:
        print(f"\n{_describe(request)}")
        answer = input("     approve? [y/N] ").strip().lower()
        if answer in APPROVE:
            decisions.append({"type": "approve"})
            continue
        if answer not in REJECT:
            print("     Unrecognised answer — treating as reject.")
        reason = input("     reason (optional): ").strip()
        decision: dict[str, Any] = {"type": "reject"}
        if reason:
            decision["message"] = reason
        decisions.append(decision)
    return decisions


def _run_turn(agent: Any, payload: Any, config: dict[str, Any]) -> str:
    """Invoke the agent, pausing for approval whenever it interrupts."""
    from langgraph.types import Command

    result = agent.invoke(payload, config=config)
    while result.get("__interrupt__"):
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


def _add_global_flags(parser: argparse.ArgumentParser, *, suppress: bool = False) -> None:
    """Register the global flags.

    `suppress` is for the parent shared by the subcommands: with `SUPPRESS` defaults the
    subparser leaves the attribute alone when the flag is absent, so a flag typed *before*
    the subcommand is not overwritten by the subparser's own default.
    """
    unset: Any = argparse.SUPPRESS if suppress else None
    parser.add_argument("--calendar", default=unset, help="Calendar id (default: primary)")
    parser.add_argument("--timezone", default=unset, help="IANA timezone, e.g. Europe/Rome")
    parser.add_argument(
        "--read-only",
        action="store_true",
        default=argparse.SUPPRESS if suppress else False,
        help="Load no write tools",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        default=argparse.SUPPRESS if suppress else False,
        help="Validate writes without sending them",
    )


def build_parser() -> argparse.ArgumentParser:
    # The global flags live on both the top-level parser and a parent shared by every
    # subcommand, so `--dry-run chat` and `chat --dry-run` both work. argparse otherwise
    # accepts them only before the subcommand, which is not where people type them.
    shared = argparse.ArgumentParser(add_help=False)
    _add_global_flags(shared, suppress=True)

    parser = argparse.ArgumentParser(
        prog="deepagents-gcal",
        description="A deepagents agent with Google Calendar tools.",
    )
    _add_global_flags(parser)

    sub = parser.add_subparsers(dest="command", required=True)

    sub.add_parser("auth", parents=[shared], help="Run the OAuth consent flow and cache the token")
    sub.add_parser("doctor", parents=[shared], help="Show resolved configuration and check credentials")
    sub.add_parser("tools", parents=[shared], help="List the tools the agent will receive")

    for name, help_text in (("ask", "Ask one question"), ("chat", "Interactive session")):
        cmd = sub.add_parser(name, parents=[shared], help=help_text)
        if name == "ask":
            cmd.add_argument("prompt", help="What to ask the agent")
        cmd.add_argument("--model", help="Model id, e.g. anthropic:claude-sonnet-5")
        cmd.add_argument("--thread", default="cli", help="Conversation thread id")
        cmd.add_argument("--no-approval", action="store_true", help="Do not pause before writes")
        cmd.add_argument("--no-subagent", action="store_true", help="Disable the research subagent")

    return parser


def load_dotenv_if_available() -> None:
    """Load a local .env when python-dotenv is installed (the `dotenv` extra).

    Without it `GCAL_*` has to come from the real environment; the README says so, and
    `doctor` shows what actually resolved.
    """
    try:
        from dotenv import load_dotenv
    except ImportError:
        return
    load_dotenv()


def main(argv: list[str] | None = None) -> int:
    load_dotenv_if_available()
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
