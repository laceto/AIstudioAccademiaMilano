"""Give jobs created before the retention policy existed an expire_at.

New jobs get expire_at when they are submitted (gateway/pipeline_adapter.py). Jobs already in
the store have none, so Firestore's TTL policy would never delete them. This sets it, using
the one retention number in gateway/retention.py (JOB_RETENTION_DAYS, default 90):

  * FINISHED jobs (delivered, discarded, rejected, classified): created_at + retention.
    Older than the retention? They are deleted at the next TTL sweep, typically within ~24 h.
  * PENDING jobs (every other status: needs_review, approved, running, awaiting_review,
    delivering, failed, queued, and any status this script does not know): now + retention.
    A full fresh period, so Luigi can still act on them. created_at + retention would delete
    a request that is still waiting for him.

DRY RUN BY DEFAULT: nothing is written without --apply.

    python -m scripts.backfill_job_expiry                    # JOB_STORE from the environment
    python -m scripts.backfill_job_expiry --apply
    JOB_STORE=firestore FIRESTORE_PROJECT=aistudio-milano python -m scripts.backfill_job_expiry

Only counts per status are printed, never what customers typed. Each write goes through
store.transition, so a job whose status changed while the script ran is skipped, not
overwritten: run it again.
"""

from __future__ import annotations

import argparse
import sys
from collections import Counter
from datetime import datetime, timezone

from gateway.jobstore import JobStore, make_store
from gateway.retention import expiry_for, retention_days

# A job in one of these statuses has nothing left to do. Anything else counts as pending.
TERMINAL_STATUSES = frozenset({"delivered", "discarded", "rejected", "classified"})


def backfill(store: JobStore, apply: bool = False, now: str | None = None) -> Counter:
    """Set expire_at on jobs that lack it. Returns counts; writes only when `apply` is true.

    Besides the totals, counts has "missing:<status>" and "updated:<status>" per status.
    `now` (ISO-8601) is for tests; it defaults to the current time.
    """
    now = now or datetime.now(timezone.utc).isoformat()
    counts: Counter = Counter()
    for job in store.all_jobs():  # a list: nothing is written while a stream is open
        counts["seen"] += 1
        if job.get("expire_at"):
            counts["already_set"] += 1
            continue
        status = job.get("status")
        counts["missing"] += 1
        counts[f"missing:{status}"] += 1
        if not job.get("created_at"):
            counts["no_created_at"] += 1  # expiry_for counts it from now
        if not apply:
            continue
        basis = job.get("created_at") if status in TERMINAL_STATUSES else now
        done = store.transition(job["job_id"], status, {"expire_at": expiry_for(basis)})
        counts["updated" if done is not None else "changed_meanwhile"] += 1
        if done is not None:
            counts[f"updated:{status}"] += 1
    for key in ("updated", "changed_meanwhile"):
        counts.setdefault(key, 0)
    return counts


def _breakdown_lines(counts: Counter, apply: bool) -> list[str]:
    lines = []
    statuses = sorted(k.split(":", 1)[1] for k in counts if k.startswith("missing:"))
    for status in statuses:
        rule = "creation + retention" if status in TERMINAL_STATUSES else "fresh period (now + retention)"
        done = f", updated {counts[f'updated:{status}']}" if apply else ""
        lines.append(f"    {status:<18} {counts[f'missing:{status}']:>5} missing{done}  -> {rule}")
    return lines


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--apply", action="store_true", help="write the changes (default: dry run)")
    parser.add_argument("--queue-dir", default="gateway/queue", help="folder of the file backend")
    args = parser.parse_args(argv)

    store = make_store(args.queue_dir)
    counts = backfill(store, apply=args.apply)

    mode = "APPLY" if args.apply else "DRY RUN (nothing written; use --apply)"
    print(f"{mode} on {type(store).__name__}, retention {retention_days()} days")
    print(f"  jobs seen:              {counts['seen']}")
    print(f"  already have expire_at: {counts['already_set']}")
    print(f"  missing expire_at:      {counts['missing']}")
    for line in _breakdown_lines(counts, args.apply):
        print(line)
    if counts["no_created_at"]:
        print(f"    of which no created_at (expiry counted from now): {counts['no_created_at']}")
    if args.apply:
        print(f"  updated:                {counts['updated']}")
        if counts["changed_meanwhile"]:
            print(f"  skipped, status changed meanwhile: {counts['changed_meanwhile']} (run again)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
