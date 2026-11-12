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
pip install -e ".[anthropic]"          # from a checkout — this is how you install it today
pip install -e ".[anthropic,dev,dotenv]"   # plus test deps and .env loading
```

Not yet published to an index, so `pip install deepagents-gcal` does not resolve — install
from a checkout (or a git URL) until it is.

Python 3.11+. Model providers are extras — pick `anthropic`, `openai`, or install your own
LangChain chat model package. Installing without one and calling `create_calendar_agent()`
raises an ImportError telling you which extra you need.

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
jailbroken prompt cannot talk its way past them. `require_approval` is orchestration: turning
it off means an unattended agent can change a real calendar, so pair it with `dry_run` in
testing and with an allowlist in production.

**`calendar_id` alone is a default, not a boundary.** Google's `calendar.events` scope is
account-wide and every tool takes a `calendar_id`, so an agent can name any calendar the
account can reach. To actually contain it, set an allowlist — enforced in the client, like
the other two:

```python
client = GoogleCalendarClient.from_env(
    calendar_id="agent@studio.it",
    allowed_calendar_ids=["agent@studio.it"],   # or GCAL_ALLOWED_CALENDAR_IDS
)
```

Any call naming another calendar then fails with `CalendarNotAllowedError` before a request
is built.

**Event text is untrusted input.** Google files emailed invitations straight into the primary
calendar, so anyone who can email the user can put text in the agent's context. The tools
label event content as data in every payload that carries it, the system prompts tell the
agent never to follow instructions found there, and free text is truncated. That is
mitigation, not a guarantee — with `require_approval=False` there is no human between an
injected instruction and a calendar write, so keep approval on when the calendar receives
mail from outside.

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
| `GCAL_ALLOWED_CALENDAR_IDS` | — | Comma-separated allowlist; any other calendar is refused |
| `GCAL_TIMEZONE` | `Europe/Rome` | IANA zone for parsing and display |
| `GCAL_READ_ONLY` | `false` | Load no write tools |
| `GCAL_DRY_RUN` | `false` | Validate writes without sending them |
| `GCAL_MAX_RESULTS` | `25` | Cap on events returned per listing |
| `GCAL_MAX_RETRIES` | `2` | Retries for transient Google failures (429/5xx) |
| `GCAL_WORK_START` / `GCAL_WORK_END` | `9` / `18` | Working hours for `find_free_slots` |
| `GCAL_AGENT_MODEL` | `anthropic:claude-sonnet-5` | Default model id |

Copy `.env.example` to `.env` as a starting point. Nothing reads that file automatically
unless you install the `dotenv` extra (`pip install -e ".[dotenv]"`), which makes the CLI
load it at startup; otherwise export the variables yourself (`set -a; . ./.env; set +a`) or
let your process manager do it. `deepagents-gcal doctor` prints what actually resolved.
Never commit `.env` or either credential file — the package ships a `.gitignore` covering
them.

## Development

```bash
pip install -e ".[dev,anthropic]"
pytest                    # 160 tests, fully offline — a fake Google service, no network, no key
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

## Known limitations

- **Listings are capped, not exhaustive.** `list_events` follows pagination up to
  `max_results` (≤250) and sets `"truncated": true` when it stops there. Narrow the window
  rather than assuming you saw everything.
- **All-day events usually do not block free slots.** Google's freebusy endpoint honours
  event transparency, and all-day events default to *free* — so a full-day holiday will not
  remove those hours from `find_free_slots` unless it is marked busy.
- **Approval state is in memory by default.** The auto-provisioned `InMemorySaver` cannot
  resume a pending approval after a restart, and a second worker will not see the thread.
  Pass `SqliteSaver` or `PostgresSaver` for anything long-lived.
- **No recurring-event creation.** Recurring events are read (expanded into instances), but
  `create_event` does not write an RRULE series.
- **No request timeout.** A hung Google request blocks the agent; set one on a service object
  you build yourself if that matters to you.

## Releasing

Versions follow semver in `pyproject.toml`; `__version__` in `src/deepagents_gcal/__init__.py`
must match. To cut a release: bump both, run `pytest` and `ruff check src tests examples`,
build with `pip wheel . --no-deps -w dist/`, and install the wheel into an empty virtualenv
before publishing it anywhere.

Rollback, if a bad version ships: a package index will not let you re-upload a version, so
**yank the bad one and release a fixed patch version** — never reuse the number. Consumers
who pinned it need the new version; consumers on a range get it automatically once the bad
one is yanked.

## License

MIT — see [LICENSE](LICENSE).
