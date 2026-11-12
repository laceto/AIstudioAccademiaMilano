"""CLI:  python -m mailagent <scan|sweep|tidy|todos|proposals|approve|reject|auth|schedule> [...]"""

from __future__ import annotations

import argparse
import sys

from dotenv import load_dotenv

from .config import load_accounts
from .extractor import LLMExtractor, openai_complete
from .pipeline import approve_proposal, reject_proposal, scan_all, sweep_account, tidy_account
from .providers import build_calendar, build_mail
from .schedule import scan_hours
from .store import JsonStore

DEFAULT_ACCOUNTS = "config/mailagent_accounts.yaml"
DEFAULT_STORE = "data/mailagent"


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="mailagent")
    ap.add_argument("--accounts", default=DEFAULT_ACCOUNTS)
    ap.add_argument("--store", default=DEFAULT_STORE)
    sub = ap.add_subparsers(dest="cmd", required=True)
    sc = sub.add_parser("scan")
    sc.add_argument("--account", help="one account id (default: all enabled)")
    sc.add_argument("--dry-run", action="store_true", help="extract and print; write nothing")
    sw = sub.add_parser("sweep", help="one-time: apply filing rules to mail already in the inbox")
    sw.add_argument("--account", help="one account id (default: all enabled)")
    sw.add_argument("--dry-run", action="store_true")
    td = sub.add_parser("tidy", help="file newsletters / notifications / promotions by header (accounts with tidy.enabled)")
    td.add_argument("--account", help="one account id (default: all tidy-enabled)")
    td.add_argument("--dry-run", action="store_true", help="print every decision and its reason; change nothing")
    sub.add_parser("todos")
    sub.add_parser("proposals")
    for name in ("approve", "reject", "auth"):
        sub.add_parser(name).add_argument("target")
    sub.add_parser("schedule")
    args = ap.parse_args(argv)
    load_dotenv()  # OPENAI_API_KEY and friends from the repo's .env

    accounts = load_accounts(args.accounts)
    by_id = {a.id: a for a in accounts}
    store = JsonStore(None if getattr(args, "dry_run", False) else args.store)

    if args.cmd == "scan":
        picked = [by_id[args.account]] if args.account else accounts
        extractor = LLMExtractor(openai_complete())
        for r in scan_all(picked, build_mail, extractor, store, dry_run=args.dry_run):
            print(f"[{r.account_id}] seen={r.seen} todos={r.new_todos} proposals={r.new_proposals} filed={r.filed} skipped={r.skipped} errors={len(r.errors)}")
            for e in r.errors:
                print(f"   ! {e}")
        if args.dry_run:
            for t in store.list_todos():
                print(f"  todo   {t['id']}: {t['title']} (due {t['due']})")
            for p in store.list_proposals():
                print(f"  event? {p['id']}: {p['title']} @ {p['start']}")
    elif args.cmd == "sweep":
        for a in [by_id[args.account]] if args.account else accounts:
            counts = sweep_account(a, build_mail(a), dry_run=args.dry_run)
            verb = "would file" if args.dry_run else "filed"
            print(f"[{a.id}] " + (", ".join(f"{verb} {n} -> {lbl}" for lbl, n in counts.items()) or "nothing to do"))
    elif args.cmd == "tidy":
        for a in [by_id[args.account]] if args.account else [a for a in accounts if a.tidy.get("enabled")]:
            r = tidy_account(a, build_mail(a), dry_run=args.dry_run)
            verb = "would file" if args.dry_run else "filed"
            print(f"[{a.id}] examined={r.examined} kept={r.kept} {verb}: " + (", ".join(f"{n} -> {l}" for l, n in r.filed.items()) or "nothing"))
            for d in r.decisions if args.dry_run else []:
                print(f"  {d['label']:<12} {d['reason']:<28} {d['sender'][:40]:<40} {d['subject'][:60]}")
            for e in r.errors:
                print(f"   ! {e}")
    elif args.cmd == "todos":
        for t in store.list_todos("open"):
            print(f"{t['id']}  {t['title']}  due={t['due']}  [{t['source_subject']}]")
    elif args.cmd == "proposals":
        for p in store.list_proposals("pending"):
            print(f"{p['id']}  {p['title']}  {p['start']}  [{p['source_subject']}]")
    elif args.cmd in ("approve", "reject"):
        acct = by_id[args.target.split(":", 1)[0]]
        if args.cmd == "approve":
            print("created", approve_proposal(args.target, store, build_calendar(acct)))
        else:
            reject_proposal(args.target, store)
    elif args.cmd == "auth":
        from .providers.google_auth import interactive_auth

        print("token saved to", interactive_auth(by_id[args.target]))
    elif args.cmd == "schedule":
        for a in accounts:
            print(f"{a.id}: {a.scans_per_day}/day at hours {scan_hours(a.scans_per_day)} ({a.timezone})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
