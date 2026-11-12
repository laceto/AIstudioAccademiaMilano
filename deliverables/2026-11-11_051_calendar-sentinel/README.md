# Calendar Sentinel (051)

Watches a Google Calendar and sends a Telegram message when a **new** event is added.
Code: `calendarsentinel/`. Tests: `tests/test_calendarsentinel.py` (17, offline).

## Setup (once)

1. Google Cloud: enable the Calendar API, create an OAuth client (Desktop), save it as `credentials/google_credentials.json`.
2. `python -m calendarsentinel auth` — browser consent, **read-only** scope (`calendar.readonly`); token saved to `credentials/calendar_sentinel_token.json` (git-ignored).
3. `.env`: `TELEGRAM_BOT_TOKEN` and `NOTIFY_TELEGRAM_CHAT_IDS` (same variables as the gateway).
4. `python -m calendarsentinel run --test-message` — checks Telegram.
5. `python -m calendarsentinel run` — **first run is a silent baseline** (existing events are not "new").

## Run

`python -m calendarsentinel run` does one polling pass. Schedule it every 5–15 minutes:

- Windows: Task Scheduler, action `python -m calendarsentinel run`, start in the repo folder.
- Linux/Cloud: cron or Cloud Scheduler. Headless token: put the token JSON in `CALENDAR_SENTINEL_TOKEN`
  (and keep `SENTINEL_STATE` on persistent storage — the state file is what remembers what was seen).

Options: `--calendar <id>` (default `primary`; use the calendar's address for another one),
`--state <path>`, `--dry-run` (prints what would be notified, sends and saves nothing).

## How it decides "new"

Incremental sync (`syncToken`) returns only changed events; an event is new if its id was never seen.
Edits are ignored, cancellations are forgotten. A recurring series is one event, so one notification.
If Telegram fails, the already-sent events are remembered and the rest is retried on the next run.
A stale sync token (410) triggers a full resync, diffed against the known ids.

## Limits

- Polling, not push: delay = your schedule interval. Calendar push (`events.watch`) needs a public HTTPS URL; not built.
- Events added by invitation appear when they hit your calendar, like any other.
- Not tried against a real calendar or Telegram yet: only the offline tests ran.
