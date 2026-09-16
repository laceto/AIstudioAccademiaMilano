# deepagents-gcal

A [deepagents](https://github.com/langchain-ai/deepagents) agent with Google Calendar tools,
packaged for reuse: install it, point it at a Google account, and you have an agent that can
read a schedule, find free slots, and create or change events — with a human approval gate on
every write.

The calendar tools are plain LangChain `StructuredTool`s, so you can also ignore the agent and
drop them into your own graph.

---

## Install

```bash
pip install deepagents-gcal            # from a package index
pip install -e ".[anthropic,dev]"      # from a checkout, with a model provider and test deps
```

Python 3.11+. Model providers are extras — pick `anthropic`, `openai`, or install your own
LangChain chat model package.

## Google setup (once)

1. [Google Cloud Console](https://console.cloud.google.com/) → create or pick a project.
2. **APIs & Services → Library** → enable **Google Calendar API**.
3. **APIs & Services → Credentials** → *Create credentials* → **OAuth client ID** →
   application type **Desktop app** → download the JSON as `credentials.json`.
4. Run the consent flow once; the token is cached with `0600` permissions:

```bash
export GCAL_CREDENTIALS_FILE=./credentials.json
deepagents-gcal auth
deepagents-gcal doctor     # verifies the resolved config and that credentials load
```

For servers and containers, either mount a service-account key
(`GCAL_SERVICE_ACCOUNT_FILE`, plus `GCAL_SUBJECT` for domain-wide delegation) or pass the
authorised-user token inline as `GCAL_TOKEN_JSON` — no writable disk required.

## Quick start

```python
from deepagents_gcal import create_calendar_agent

agent = create_calendar_agent()          # reads GCAL_* from the environment

result = agent.invoke(
    {"messages": [{"role": "user", "content": "Find me an hour with Mario next week"}]},
    config={"configurable": {"thread_id": "luigi-demo"}},
)
print(result["messages"][-1].content)
```

From the shell:

```bash
deepagents-gcal ask "what's on my calendar tomorrow?"
deepagents-gcal chat --dry-run
deepagents-gcal tools
```

### Just the tools, in your own agent

```python
from deepagents_gcal import GoogleCalendarClient, build_calendar_tools
from deepagents import create_deep_agent

client = GoogleCalendarClient.from_env(read_only=True)
agent = create_deep_agent(model="anthropic:claude-sonnet-5", tools=build_calendar_tools(client))
```

### Just the client, no LLM at all

```python
from deepagents_gcal import GoogleCalendarClient, EventDraft

client = GoogleCalendarClient.from_env()
for event in client.list_events(time_min="today", time_max="+7d"):
    print(event.summary, event.start)

client.create_event(EventDraft(summary="Retro", start="2026-09-18T16:00", duration_minutes=45))
```

`client`, `models`, `scheduling` and `timeutils` import without LangChain; only `agent`, `tools`
and `cli` pull it in.

---

## Tools

| Tool | Kind | What it does |
|------|------|--------------|
| `current_time` | read | Current date/time/weekday in the configured zone — the agent calls this before resolving anything relative |
| `list_calendars` | read | Calendars the account can access, with ids and access roles |
| `list_events` | read | Events in a window, recurrences expanded, ordered by start |
| `search_events` | read | Full-text search around today |
| `get_event` | read | One event in full, by id |
| `find_free_slots` | read | Gaps long enough for a meeting, across one or more calendars, inside working hours |
| `create_event` | **write** | Create an event (attendees, reminders, all-day, optional invitation emails) |
| `update_event` | **write** | Patch title, time, description or location |
| `delete_event` | **write** | Delete an event |

Every tool returns JSON with an `ok` flag; failures come back as
`{"ok": false, "error": "...", "error_type": "..."}` so the model can correct itself instead of
stalling.

Times accept ISO 8601 (`2026-09-17T10:00`), a bare date (`2026-09-17`), the keywords
`now` / `today` / `tomorrow` / `yesterday`, or offsets like `+2h`, `-30m`, `+3d`, `+1w`.

## Agent shape

`create_calendar_agent()` wraps `create_deep_agent` with:

- **the calendar toolset**, bound to a client you inject or one built from the environment;
- **a `schedule-researcher` subagent** (read-only) for bulk investigation — "find every meeting
  with Acme this quarter" — so raw event dumps stay out of the main context window;
- **human-in-the-loop approval** on `create_event`, `update_event` and `delete_event`, with an
  `InMemorySaver` provisioned automatically because LangGraph interrupts need a checkpointer;
- deepagents' own planning (`write_todos`) and filesystem middleware, untouched.

Handling an approval interrupt yourself:

```python
from langgraph.types import Command

result = agent.invoke({"messages": [...]}, config=config)
if result.get("__interrupt__"):
    request = result["__interrupt__"][0].value["action_requests"][0]
    print(request["name"], request["args"])          # show it to a human
    result = agent.invoke(Command(resume={"decisions": [{"type": "approve"}]}), config=config)
```

Allowed decisions are `approve`, `edit` (supply `edited_action`) and `reject` (optional
`message`). Pass `require_approval=False` for unattended runs — see the trade-off below.

## Three ways to keep it safe

| Setting | Effect |
|---------|--------|
| `read_only=True` | Requests read-only OAuth scopes, refuses writes at the client, and never even builds the write tools |
| `dry_run=True` | Validates a write fully, then returns a preview instead of calling the API — the mode to demo in |
| `require_approval=True` (default) | Interrupts before each write so a human approves, edits or rejects it |

`read_only` and `dry_run` are enforced in `GoogleCalendarClient`, below the tool layer, so a
jailbroken prompt cannot talk its way past them. `require_approval` is orchestration: turning it
off means an unattended agent can change a real calendar, so pair it with `dry_run` in testing
and with a narrow, non-primary `calendar_id` in production.

Other guarantees worth knowing:

- Scopes follow least privilege: `calendar.readonly` alone in read-only mode.
- Attendee invitations are opt-in (`notify_attendees`), so a mistake stays private.
- Tokens are written `0600`, never logged, and `describe()` redacts everything secret.
- `credentials.json` / `token.json` belong in `.gitignore` — they are secrets.

## Configuration

Every setting comes from a `GCAL_*` environment variable, an argument to
`CalendarSettings(...)`, or an override on `from_env(...)` (highest wins).

| Variable | Default | Meaning |
|----------|---------|---------|
| `GCAL_CREDENTIALS_FILE` | `credentials.json` | OAuth client-secrets file |
| `GCAL_TOKEN_FILE` | `token.json` | Where the cached user token lives |
| `GCAL_TOKEN_JSON` | — | Authorised-user token as inline JSON (containers) |
| `GCAL_SERVICE_ACCOUNT_FILE` | `$GOOGLE_APPLICATION_CREDENTIALS` | Service-account key |
| `GCAL_SUBJECT` | — | Impersonated user for domain-wide delegation |
| `GCAL_CALENDAR_ID` | `primary` | Default calendar |
| `GCAL_TIMEZONE` | `Europe/Rome` | IANA zone for parsing and display |
| `GCAL_READ_ONLY` | `false` | Load no write tools |
| `GCAL_DRY_RUN` | `false` | Validate writes without sending them |
| `GCAL_MAX_RESULTS` | `25` | Default page size for listings |
| `GCAL_WORK_START` / `GCAL_WORK_END` | `9` / `18` | Working hours for `find_free_slots` |
| `GCAL_AGENT_MODEL` | `anthropic:claude-sonnet-5` | Default model id |

Copy `.env.example` to `.env` as a starting point. Never commit either credential file.

## Development

```bash
pip install -e ".[dev,anthropic]"
pytest                    # 100+ tests, fully offline — a fake Google service, no network, no key
ruff check src tests
```

The test suite injects a fake service object into `GoogleCalendarClient`, so the real request
path is exercised without credentials. Extending the package follows the same shape: add a
method to the client, expose it in `build_calendar_tools`, and add it to `WRITE_TOOL_NAMES` if it
mutates anything — the approval gate is derived from that tuple.

Layout:

```
src/deepagents_gcal/
├── agent.py       create_calendar_agent — deepagents wiring, subagent, approval gate
├── tools.py       LangChain tools + argument schemas
├── client.py      GoogleCalendarClient — typed API wrapper, read-only/dry-run guards
├── models.py      CalendarRef, Event, EventDraft, FreeSlot
├── scheduling.py  pure free-slot arithmetic
├── timeutils.py   forgiving datetime parsing
├── auth.py        OAuth / service-account / inline-token credential loading
├── config.py      CalendarSettings
├── prompts.py     system prompts
└── cli.py         deepagents-gcal entry point
```

## License

MIT — see [LICENSE](LICENSE).
