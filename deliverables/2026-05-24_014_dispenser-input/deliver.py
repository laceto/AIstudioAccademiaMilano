"""Operator CLI for the dispenser queue.

Run from `deliverables/2026-05-24_014_dispenser-input/`.

Commands:
    python deliver.py list                          # show pending requests
    python deliver.py show <request_id>             # full record for one request
    python deliver.py notify <request_id>           # ping admin via Telegram
    python deliver.py send <request_id> <file>      # send the output file to the user
                                                    # and mark the request done

Typical operator flow:
    1. New paid request lands → `python deliver.py list` (or admin gets a Telegram ping)
    2. Build the deliverable using the 6-agent pipeline (Stacy → Francesca)
    3. `python deliver.py send <id> <path/to/output.md|.pdf>` → user gets it on
       their chosen channel(s) and the queue row is closed.
"""
import os
import sys
from pathlib import Path

import request_queue
from delivery import CHANNELS, get_channel

ADMIN_TELEGRAM_CHAT_ID = os.environ.get("ADMIN_TELEGRAM_CHAT_ID")


def cmd_list(_args: list[str]) -> int:
    pending = request_queue.list_all("pending")
    if not pending:
        print("No pending requests.")
        return 0
    for item in pending:
        cls = item.get("classification", {})
        print(
            f"{item['id'][:8]}  "
            f"€{cls.get('price_eur', '?')}  "
            f"{cls.get('product_label', '?')}  "
            f"→ {','.join(item.get('delivery_channels', []))} "
            f"({item.get('recipient', '?')})"
        )
    return 0


def cmd_show(args: list[str]) -> int:
    if not args:
        print("usage: deliver.py show <request_id>", file=sys.stderr)
        return 2
    item = request_queue.get(args[0]) or _find_by_prefix(args[0])
    if not item:
        print(f"No request matching {args[0]!r}", file=sys.stderr)
        return 1
    import json
    print(json.dumps(item, indent=2, default=str))
    return 0


def cmd_notify(args: list[str]) -> int:
    if not ADMIN_TELEGRAM_CHAT_ID:
        print("ADMIN_TELEGRAM_CHAT_ID not set; aborting.", file=sys.stderr)
        return 2
    if not args:
        pending = request_queue.list_all("pending")
        if not pending:
            print("No pending requests to notify about.")
            return 0
        summary = "\n".join(
            f"• `{i['id'][:8]}` €{i['classification']['price_eur']} {i['classification']['product_label']}"
            for i in pending
        )
        message = f"*Dispenser pending queue* ({len(pending)})\n{summary}"
    else:
        item = request_queue.get(args[0]) or _find_by_prefix(args[0])
        if not item:
            print(f"No request matching {args[0]!r}", file=sys.stderr)
            return 1
        cls = item["classification"]
        message = (
            f"*New paid request* `{item['id'][:8]}`\n"
            f"Product: *{cls['product_label']}* €{cls['price_eur']}\n"
            f"Dispenser: `{item.get('dispenser_id', '?')}`\n"
            f"Channels: {', '.join(item.get('delivery_channels', []))}\n"
            f"Recipient: `{item.get('recipient', '?')}`\n"
            f"Details: {cls['extras'].get('free_text', '(none)')}"
        )
    tg = get_channel("telegram")
    tg.send(ADMIN_TELEGRAM_CHAT_ID, message)
    print("Notified admin.")
    return 0


def cmd_send(args: list[str]) -> int:
    if len(args) < 2:
        print("usage: deliver.py send <request_id> <file>", file=sys.stderr)
        return 2
    rid_or_prefix, file_arg = args[0], args[1]
    item = request_queue.get(rid_or_prefix) or _find_by_prefix(rid_or_prefix)
    if not item:
        print(f"No request matching {rid_or_prefix!r}", file=sys.stderr)
        return 1
    body = Path(file_arg).read_text()
    failures: list[str] = []
    for ch_name in item.get("delivery_channels", []):
        try:
            channel = get_channel(ch_name)
            channel.send(item["recipient"], body)
            print(f"  ✓ sent via {ch_name}")
        except Exception as e:
            failures.append(f"{ch_name}: {type(e).__name__}: {e}")
            print(f"  ✗ {ch_name} failed: {e}", file=sys.stderr)
    if failures:
        request_queue.update_status(item["id"], "failed", failures=failures)
        return 1
    request_queue.update_status(item["id"], "done", delivered_from=file_arg)
    print(f"Marked {item['id'][:8]} done.")
    return 0


def _find_by_prefix(prefix: str) -> dict | None:
    matches = [i for i in request_queue.list_all() if i["id"].startswith(prefix)]
    if len(matches) == 1:
        return matches[0]
    return None


COMMANDS = {"list": cmd_list, "show": cmd_show, "notify": cmd_notify, "send": cmd_send}


def main() -> int:
    if len(sys.argv) < 2 or sys.argv[1] not in COMMANDS:
        print(__doc__, file=sys.stderr)
        return 2
    return COMMANDS[sys.argv[1]](sys.argv[2:])


if __name__ == "__main__":
    raise SystemExit(main())
