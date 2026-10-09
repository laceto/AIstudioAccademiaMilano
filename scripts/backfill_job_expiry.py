"""Give jobs created before the retention policy existed an expire_at.

New jobs get expire_at when they are submitted (gateway/pipeline_adapter.py). Jobs already in
the store have none, so Firestore's TTL policy would never delete them. This sets it from
created_at (gateway/retention.py: created_at + JOB_RETENTION_DAYS, default 90). Jobs older than
the retention period therefore expire at the next TTL sweep, typically within about 24 hours.

DRY RUN BY DEFAULT: nothing is written without --apply.

    python -m scripts.backfill_job_expiry                    # JOB_STORE from the environment
    python -m scripts.backfill_job_expiry --apply
    JOB_STORE=firestore FIRESTORE_PROJECT=aistudio-milano python -m scripts.backfill_job_expiry

Only counts are printed, never what customers typed. Each write goes through store.transition,
so a job whose status changed while the script ran is skipped, not overwritten: run it again.
"""

from __future__ import annotations

import argparse
import sys
from collections import Counter
from typing import Iterator

from gateway.jobstore import FileJobStore, FirestoreJobStore, JobStore, _from_storage, make_store
from gateway.retention import expiry_for, retention_days


def all_jobs(store: JobStore) -> Iterator[dict]:
    """Every job in the store, whatever its status (the JobStore contract lists by status only)."""
    if isinstance(store, FileJobStore):
        for path in sorted(store.queue_dir.glob("*.json")):
            job = store.get(path.stem)
            if job is not None:
                yield job
    elif isinstance(store, FirestoreJobStore):
        for snap in store._collection().stream():
            yield _from_storage(snap.to_dict())
    else:
        raise TypeError(f"cannot list every job of a {type(store).__name__}")


def backfill(store: JobStore, apply: bool = False) -> Counter:
    """Set expire_at on jobs that lack it. Returns counts; writes only when `apply` is true."""
    counts: Counter = Counter()
    # Materialise first: do not write to the collection while streaming it.
    for job in list(all_jobs(store)):
        counts["seen"] += 1
        if job.get("expire_at"):
            counts["already_set"] += 1
            continue
        counts["missing"] += 1
        if not job.get("created_at"):
            counts["no_created_at"] += 1  # expiry_for counts it from now
        if not apply:
            continue
        done = store.transition(job["job_id"], job.get("status"), {"expire_at": expiry_for(job.get("created_at"))})
        counts["updated" if done is not None else "changed_meanwhile"] += 1
    for key in ("updated", "changed_meanwhile"):
        counts.setdefault(key, 0)
    return counts


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
    if counts["no_created_at"]:
        print(f"    of which no created_at (expiry counted from now): {counts['no_created_at']}")
    if args.apply:
        print(f"  updated:                {counts['updated']}")
        if counts["changed_meanwhile"]:
            print(f"  skipped, status changed meanwhile: {counts['changed_meanwhile']} (run again)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
