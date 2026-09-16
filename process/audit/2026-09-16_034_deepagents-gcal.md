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
      QA pass — see qa_result. 123/123 package tests and 8/8 repo contract tests green;
      no credentials in code; token files gitignored; README claims verified against code.
    duration_sec: 120
    status: ok
  - name: Technical Auditor
    role: risk_agent
    action: >
      Code, security and architecture review of the package; Risk Units scored below.
    duration_sec: 120
    status: ok
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
qa_result: pass
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

123 tests in the package (`pytest` from the package root) plus 8 repo contract tests in
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

## Open follow-ups

- Real-credential smoke test once Luigi runs `deepagents-gcal auth` (D007 already has the
  Google client-secrets flow documented in `credentials/registry.md`)
- Recurring-event creation (RRULE) — deliberately out of scope for 0.1.0; the client reads
  recurring events expanded, but cannot create a series
- Publishing to an index: the package is pip-installable from the repo path today; PyPI
  (or a private index) is a Luigi decision, not an agent one
- `GCAL_TIMEZONE` defaults to `Europe/Rome` — studio-centric, and the right default for
  this studio's clients, but worth revisiting if the package is published publicly
