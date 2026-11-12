---
request_id: "034"
date: "2026-09-16"
intent: calendar_integration
product_type: calendar_integration
outcome: success
price: "14.90"
invoice_id: "—"
agents_invoked:
  - name: Stacy
    role: intent_classifier
    action: >
      Classified as calendar_integration (14.90, priced tier — no unknown_product block).
      Flagged the OAuth dependency: Google Calendar write scope, consent flow owned by
      Luigi, never by an agent session.
    duration_sec: 4
    status: ok
  - name: agentic-router
    role: framework_gate
    action: >
      STEP 2 gate. Routed to deep-agents-core, deep-agents-orchestration,
      langgraph-subagents, langgraph-persistence, langchain-fundamentals — all loaded
      before any implementation code was written.
    duration_sec: 6
    status: ok
  - name: Gianni
    role: technical_scoper
    action: >
      Scoped as a distributable package (src layout, hatchling, console entry point)
      rather than a deliverable script. Pinned deepagents 0.7.x and inspected its real
      API surface (create_deep_agent, SubAgent, interrupt_on, HITL decision payloads)
      in a live install instead of writing against remembered signatures.
    duration_sec: 25
    status: ok
  - name: Chiara
    role: implementer
    action: >
      11 modules under src/deepagents_gcal/ (agent, tools, client, models, scheduling,
      timeutils, auth, config, prompts, cli, errors), 123 offline tests, README,
      4 runnable examples, LICENSE, .env.example. Repo contract test added at
      tests/test_034_deepagents_gcal.py.
    duration_sec: 900
    status: ok
  - name: Stacy QA
    role: output_validator
    action: >
      FAIL on first pass — 9 defects, all documentation/completeness: CLI flags rejected
      after the subcommand (the README's own quick-start command), all-day events built
      with a non-exclusive end date, `pip install deepagents-gcal` documented but
      unpublished, `.env` documented but never loaded, token file world-readable during
      the write, no packaged `.gitignore`, `get_event` raising an untranslated error on a
      cancelled instance. One claim rejected: the Haiku model id is valid as written.
    duration_sec: 416
    status: fail_then_fixed
  - name: Technical Auditor
    role: risk_agent
    action: >
      4.58 RU (baseline 2.4, flag 3.6) — above threshold. One P0 (documented
      `calendar_id` containment that did not hold) and five P1s: prompt injection via
      event text, freebusy reporting an unreadable calendar as free, all-day end dates,
      non-IANA Google timezones aborting a listing, undocumented release rollback.
      All P0/P1 code defects fixed and regression-tested; see Review pass below.
    duration_sec: 396
    status: fail_then_fixed
  - name: Marco
    role: transaction_manager
    action: >
      calendar_integration is an existing priced tier (14.90) — no unknown_product block,
      no escalation, no change to config/global_settings.json.
    duration_sec: 3
    status: ok
  - name: Francesca
    role: delivery_agent
    action: >
      Branch claude/langchain-deepagents-calendar-vaqqq9, audit log, deliverable folder,
      CLAUDE.md table row.
    duration_sec: 60
    status: ok
skills_used:
  - deep-agents-core
  - deep-agents-orchestration
  - langgraph-subagents
  - langgraph-persistence
  - langchain-fundamentals
  - deepagents_package_authoring
  - google_calendar_api_v3
  - langgraph_human_in_the_loop
  - python_packaging_hatchling
delivery:
  method: github
  destination: deliverables/2026-09-16_034_deepagents-gcal/
  confirmed: true
qa_result: pass_after_fixes
payment:
  amount: "14.90"
  method: pending
  receipt_id: "—"
learning_flags:
  new_skills:
    - deepagents_package_authoring
    - google_calendar_api_v3
    - python_packaging_hatchling
  new_mcp: []
  risk_score: 2
  risk_units_pre_fix: 4.58
  risk_units_flagged: true
  cost_overrun: false
  loss_development_flag: false
---

# D034 — deepagents-gcal

An installable Python package (`pip install deepagents-gcal`) that gives a
[deepagents](https://github.com/langchain-ai/deepagents) agent a Google Calendar: read the
schedule, find free slots, create/move/delete events — with a human approval gate on every
write. The calendar tools are plain LangChain `StructuredTool`s, so a consumer can take the
tools and skip our agent entirely.

This is the first thing the studio has shipped as a *package for other developers* rather
than a deliverable folder to run in place. That changed the build: src layout, hatchling
build backend, console entry point, `py.typed`, MIT license, semantic version, and a test
suite that ships with the source.

## Why the safety model has three layers, not one

Calendar writes are irreversible in the way users notice — a deleted event does not come
back, and an invitation email cannot be recalled. So the package refuses to rely on the
prompt alone:

| Layer | Where it lives | What it stops |
|-------|----------------|---------------|
| `read_only` | `GoogleCalendarClient._guard_write` + read-only OAuth scopes | Writes are impossible; the write tools are never even built |
| `dry_run` | Same guard | Writes validate fully, then return a preview instead of an API call |
| `require_approval` | `interrupt_on` → LangGraph interrupt | A human approves, edits or rejects each write |

The first two are enforced *below* the tool layer, so a jailbroken prompt cannot talk its
way past them — they are client state, not instructions. The third is orchestration and can
be switched off for unattended runs, which is exactly why the other two exist.

Least privilege is real here: read-only mode requests `calendar.readonly` alone, never
`calendar.events`. Attendee invitation emails are opt-in per call (`notify_attendees`), so
a mistaken event stays private to the calendar owner.

## Architecture note — the LLM never does date arithmetic

Every relative date the model produces ("next Tuesday", "tomorrow at 4") goes through
`timeutils.parse_datetime`, and the system prompt requires calling `current_time` before
resolving anything relative. Models are confidently wrong about what today is, and a
wrong date on a calendar write is a silent failure — it succeeds, it just books the wrong
day. Parsing accepts ISO 8601, bare dates, `now`/`today`/`tomorrow`/`yesterday`, and
offsets (`+2h`, `+1w`), and rejects everything else loudly rather than guessing.

Free-slot arithmetic lives in `scheduling.py` as pure functions over `(start, end)` tuples:
merge busy blocks, clip to working-hour windows, subtract, keep gaps at or above the
requested duration. No Google imports, no LangChain imports — the logic most likely to
double-book someone is the logic easiest to test.

## Context discipline — the research subagent

`schedule-researcher` is a read-only subagent holding the same client. Bulk questions
("every meeting with Acme this quarter") delegate to it, so hundreds of raw event JSON
blobs land in *its* context and only a written summary comes back to the main thread. This
is the deepagents subagent convention from `deep-agents-orchestration`, applied to the one
tool in this package that can flood a context window.

## Testing

160 tests in the package (`pytest` from the package root) plus 10 repo contract tests in
`tests/test_034_deepagents_gcal.py`. All offline: a fake Google service object is injected
into `GoogleCalendarClient`, so the real request-building path is exercised without a
credential or a network call.

Six of them are true end-to-end runs through the compiled LangGraph agent with a scripted
tool-calling model: the agent calls `list_events` and gets real tool output; a
`create_event` interrupts for approval and only writes after `{"type": "approve"}`; a
rejected `delete_event` leaves the calendar untouched.

Test order was not strictly test-first for the pure-logic modules — models, client and
tools were written alongside their tests rather than after them. The TDD rule in CLAUDE.md
was met in coverage, not in sequence.

**Not verified:** no call has been made against a real Google Calendar from this session.
That requires Luigi's OAuth consent, which correctly sits outside an agent session. The API
contract is written from Google Calendar API v3 documentation and exercised against a fake
that mirrors the `googleapiclient` chained-builder shape. Packaging *is* verified: the wheel
builds and installs, and the `deepagents-gcal` CLI runs from the installed entry point.

## Review pass — what the two reviews changed

Both reviews failed the first cut, and they failed it on different axes: Stacy on
documentation that did not match the code, the auditor on defects that would only show up
against the real Google API. Every claim below was reproduced before being fixed, and one
was rejected: `claude-haiku-4-5-20251001` is a valid model id, so the comment stands.

**The finding that mattered most.** The README told developers to contain the agent with a
narrow `calendar_id`. That is not containment: Google's `calendar.events` scope is
account-wide, every tool takes a `calendar_id`, and `settings.calendar_id` was only a
default — a prompt that passes `calendar_id="primary"` writes to the main calendar. Shipping
a security control that does not hold is worse than shipping none, because someone relies on
it. Fixed with a real boundary: `allowed_calendar_ids`, enforced in `_calendar()` below the
tool layer, refusing any other calendar before a request is built.

Fixed, each with a regression test:

| Finding | Fix |
|---------|-----|
| `calendar_id` documented as containment but wasn't | `allowed_calendar_ids` allowlist enforced in the client |
| Event text reached the model unlabelled (Google files emailed invitations into the primary calendar) | Untrusted-content note in every payload carrying event text, injection rules in both prompts, free text truncated |
| freebusy reported an unreadable calendar as completely free | Per-calendar `errors` now raise instead of silently returning an empty schedule |
| All-day events built a non-exclusive end date Google rejects | End date rounds up and is floored at start + 1 day |
| `GMT+02:00`-style zones aborted a whole listing | Fixed-offset zones parsed; unusable zone names fall back instead of raising |
| `+2h` was wall-clock, so it meant 3 hours across a DST fallback | Minute/hour offsets resolve through UTC; day/week offsets stay wall-clock |
| CLI rejected `chat --dry-run` — the README's first command | Global flags on a shared parent parser, `SUPPRESS` defaults so both orders win |
| Enter at the approval prompt approved an irreversible write | Approval is explicit; a bare Return rejects |
| One answer could be applied to a different pending call | One decision per action request, each prompted after the call it names |
| `update_event` broke all-day events and could invert start/end | Reads the event first, preserves its shape, carries duration when only the start moves |
| Token file was 0644 during the write | Created 0600 via `os.open`, written to a temp file, atomically renamed |
| A read-only token failed with a 403 *after* a human approved the write | Scopes verified at load time |
| Listings silently truncated at `max_results` | Pagination followed to the cap, `truncated` reported |
| `get_event` on a cancelled instance raised an untranslated error | Translated to `EventNotFoundError` |
| Transient 429/5xx became user-visible failures | `num_retries` passed to services that accept it |
| Google error bodies forwarded verbatim into model context | Clipped to 300 chars |
| `pip install deepagents-gcal` documented but unpublished; `.env` documented but never read | README corrected; optional `dotenv` extra loads it in the CLI |
| No packaged `.gitignore` — token lands in the project root when lifted out of this repo | Shipped with the package |
| Malformed `GCAL_*` values produced a traceback | Wrapped as `CalendarError`, which the CLI handles |

Tests went 124 → 160. Re-verified after the fixes: full suite green, `ruff` clean, wheel
builds, clean-virtualenv install works and `deepagents-gcal tools --read-only` runs from the
installed entry point. The re-verification was mine, not a second Stacy pass — worth knowing
when reading `qa_result: pass_after_fixes`.

## For Luigi

Three things deliberately left open rather than decided by an agent:

1. **Publishing.** The auditor withheld sign-off on any package-index release until a
   rollback procedure existed; that is now written into the README (yank + patch release,
   never reuse a version). Whether to publish at all is still your call.
2. **No request timeout** on the Google service object — a hung request blocks the agent.
   Documented under Known limitations rather than papered over.
3. **In-memory approval state** is the default. Fine for a CLI, wrong for a server: a paused
   write cannot survive a restart. The code now warns when it auto-provisions one.

## Open follow-ups

- Real-credential smoke test once Luigi runs `deepagents-gcal auth` (D007 already has the
  Google client-secrets flow documented in `credentials/registry.md`)
- Recurring-event creation (RRULE) — deliberately out of scope for 0.1.0; the client reads
  recurring events expanded, but cannot create a series
- Publishing to an index: the package is pip-installable from the repo path today; PyPI
  (or a private index) is a Luigi decision, not an agent one
- `GCAL_TIMEZONE` defaults to `Europe/Rome` — studio-centric, and the right default for
  this studio's clients, but worth revisiting if the package is published publicly
- Request timeouts and a `RecurrenceRule` for series creation, if this grows past 0.1.0
