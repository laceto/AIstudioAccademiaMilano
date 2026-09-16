"""`create_calendar_agent` — a deepagents agent wired to Google Calendar.

What this adds on top of `create_deep_agent`:

* the calendar toolset, bound to a client you can inject or let it build from env
* a read-only `schedule-researcher` subagent, so bulk event dumps stay out of the
  main context window
* human-in-the-loop approval on the three write tools, with a checkpointer
  provisioned automatically (LangGraph interrupts need one)

Every deepagents keyword argument (`middleware`, `store`, `response_format`,
`context_schema`, …) is forwarded untouched.
"""

from __future__ import annotations

import logging
import os
from typing import Any, Sequence

from deepagents import SubAgent, create_deep_agent
from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.tools import BaseTool

from .client import GoogleCalendarClient
from .config import CalendarSettings
from .prompts import CALENDAR_SYSTEM_PROMPT, RESEARCHER_DESCRIPTION, RESEARCHER_SYSTEM_PROMPT
from .tools import WRITE_TOOL_NAMES, build_calendar_tools

#: Overridable with GCAL_AGENT_MODEL, e.g. "openai:gpt-5.5" or "anthropic:claude-haiku-4-5-20251001".
DEFAULT_MODEL = "anthropic:claude-sonnet-5"

APPROVAL_DECISIONS = ["approve", "edit", "reject"]

logger = logging.getLogger(__name__)


def default_model() -> str:
    return os.environ.get("GCAL_AGENT_MODEL", DEFAULT_MODEL)


def build_interrupt_config(tool_names: Sequence[str] = WRITE_TOOL_NAMES) -> dict[str, Any]:
    """Approval gate for calendar mutations, in deepagents' `interrupt_on` format."""
    return {
        name: {
            "allowed_decisions": list(APPROVAL_DECISIONS),
            "description": f"Approve, edit or reject this {name.replace('_', ' ')} call.",
        }
        for name in tool_names
    }


def build_research_subagent(client: GoogleCalendarClient) -> SubAgent:
    """A read-only research subagent that shares the parent's credentials."""
    return SubAgent(
        name="schedule-researcher",
        description=RESEARCHER_DESCRIPTION,
        system_prompt=RESEARCHER_SYSTEM_PROMPT,
        tools=build_calendar_tools(client, include_write=False),
    )


def create_calendar_agent(
    *,
    model: str | BaseChatModel | None = None,
    client: GoogleCalendarClient | None = None,
    settings: CalendarSettings | None = None,
    tools: Sequence[BaseTool] = (),
    subagents: Sequence[Any] = (),
    read_only: bool | None = None,
    dry_run: bool | None = None,
    require_approval: bool = True,
    include_research_subagent: bool = True,
    system_prompt: str | None = None,
    checkpointer: Any | None = None,
    **deep_agent_kwargs: Any,
) -> Any:
    """Build the calendar deep agent.

    Args:
        model: Model id (`"provider:name"`) or a chat model instance.
        client: A configured client. When omitted, one is built from `settings`
            or from `GCAL_*` environment variables.
        settings: Settings used only when `client` is omitted.
        tools: Extra tools to hand the agent alongside the calendar ones.
        subagents: Extra deepagents subagents.
        read_only / dry_run: Convenience overrides applied when building the client.
        require_approval: Interrupt before every calendar mutation so a human can
            approve, edit or reject it. Ignored for read-only agents, which have
            no write tools to gate.
        include_research_subagent: Attach the read-only `schedule-researcher`.
        system_prompt: Replaces the default calendar prompt entirely.
        checkpointer: LangGraph checkpointer. Approval interrupts require one; if
            you ask for approval without providing a checkpointer, an
            `InMemorySaver` is created for you.
        **deep_agent_kwargs: Forwarded verbatim to `create_deep_agent`.

    Returns:
        A compiled LangGraph agent. Invoke it with
        `{"messages": [{"role": "user", "content": "..."}]}` and a config carrying
        a `thread_id` whenever a checkpointer is in play.
    """
    if client is None:
        overrides: dict[str, Any] = {}
        if read_only is not None:
            overrides["read_only"] = read_only
        if dry_run is not None:
            overrides["dry_run"] = dry_run
        if settings is not None:
            base = settings.model_copy(update=overrides)
        else:
            base = CalendarSettings.from_env(**overrides)
        client = GoogleCalendarClient(settings=base)
    elif read_only is not None or dry_run is not None:
        raise ValueError(
            "read_only/dry_run configure a new client; pass them via the client's "
            "settings when you supply your own client"
        )

    calendar_tools = build_calendar_tools(client)
    all_tools = [*calendar_tools, *tools]

    all_subagents: list[Any] = list(subagents)
    if include_research_subagent:
        all_subagents.insert(0, build_research_subagent(client))

    writes_exposed = [t.name for t in calendar_tools if t.name in WRITE_TOOL_NAMES]
    interrupt_on = deep_agent_kwargs.pop("interrupt_on", None)
    if interrupt_on is None and require_approval and writes_exposed:
        interrupt_on = build_interrupt_config(writes_exposed)

    if interrupt_on and checkpointer is None:
        from langgraph.checkpoint.memory import InMemorySaver

        # Interrupts need a checkpointer to resume from. An in-memory one is fine for a
        # CLI or a notebook, but a paused write cannot survive a restart or reach a second
        # worker — pass SqliteSaver/PostgresSaver for anything long-lived.
        logger.warning(
            "Approval is enabled with no checkpointer; using an in-memory one. "
            "Pending approvals will not survive a restart — pass a persistent "
            "checkpointer (SqliteSaver, PostgresSaver) in production."
        )
        checkpointer = InMemorySaver()

    try:
        return create_deep_agent(
            model=model or default_model(),
            tools=all_tools,
            system_prompt=system_prompt or CALENDAR_SYSTEM_PROMPT,
            subagents=all_subagents or None,
            interrupt_on=interrupt_on,
            checkpointer=checkpointer,
            **deep_agent_kwargs,
        )
    except ImportError as exc:
        # Model providers are optional extras, so the default model's package may be absent.
        raise ImportError(
            f"{exc}. The model provider package is not installed — try "
            "`pip install deepagents-gcal[anthropic]` (or [openai]), or pass a model "
            "instance you built yourself."
        ) from exc
