"""python -m calendarsentinel auth | run [--calendar ID] [--state PATH] [--dry-run] [--test-message]"""

from __future__ import annotations

import argparse
import os

from .notify import format_event, send_telegram


def main() -> int:
    ap = argparse.ArgumentParser(prog="calendarsentinel")
    ap.add_argument("cmd", choices=["auth", "run"])
    ap.add_argument("--calendar", default=os.environ.get("SENTINEL_CALENDAR_ID", "primary"))
    ap.add_argument("--state", default=os.environ.get("SENTINEL_STATE", "data/calendar_sentinel_state.json"))
    ap.add_argument("--dry-run", action="store_true", help="print new events, send nothing, save nothing")
    ap.add_argument("--test-message", action="store_true", help="send one Telegram message to check the channel")
    a = ap.parse_args()
    if a.cmd == "auth":
        from .auth import interactive_auth

        print("token saved to", interactive_auth())
        return 0
    if a.test_message:
        send_telegram("Calendar sentinel: test message")
        return 0
    from .auth import build_service
    from .sentinel import run_once

    new = run_once(build_service(), a.state, lambda e: send_telegram(format_event(e)), a.calendar, dry_run=a.dry_run)
    if a.dry_run:
        for e in new:
            print(format_event(e), "\n")
    print(f"{len(new)} new event(s)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
