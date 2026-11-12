---
request_id: "037"
date: "2026-10-09"
intent: internal_infra_build
product_type: retention_privacy_recovery
outcome: success
price: "0.00"
invoice_id: "—"
agents_invoked:
  - name: Claude
    role: orchestrator
    action: >
      Luigi asked for a team of agents. Three engineers ran in parallel in isolated git worktrees
      (one branch and PR each): TTL and delete protection, stuck-job recovery, privacy notice.
      A compliance agent reviewed the privacy and TTL work; two technical auditors reviewed the
      TTL work and the stuck-job work. Their findings were fixed before merging. The orchestrator
      merged in the order TTL, stuck-job recovery, privacy, resolving small conflicts in
      scripts/cloudrun_lib.sh.
    duration_sec: 0
    status: ok
  - name: Luigi
    role: operator_and_approver
    action: >
      Applied the job-expiry backfill, launched the gateway deploy that publishes the privacy
      notice, and owns the open legal inputs (controller identity, contact, DPAs).
    duration_sec: 0
    status: ok
skills_used:
  - breakdown
  - agentic-router
  - deep-agents-core
learning_flags:
  new_skills: []
  new_mcp: []
  risk_score: 2
---

# Request 037 — Data retention, privacy notice and stuck-job recovery

Internal tooling, no customer price (0.00). Deliverable folder:
`deliverables/2026-10-09_037_retention-privacy-recovery/`. Follows 036, whose "not done" list it closes
in part (TTL and delete protection, privacy notice, stuck `running` jobs).

## Outcome

Job documents, which hold user text, now expire on their own after 90 days. A job whose worker died
mid-run no longer stays in `running` forever: a scheduled sweep fails it and tells Luigi once. The bot
tells users what is stored, why, for how long and who sees it.

| Part | What | PR |
|------|------|----|
| Retention | `gateway/retention.py`: single source for how long a job is kept (`JOB_RETENTION_DAYS`, default 90) | #201 |
| TTL + protection | `expire_at` on every job (creation + 90 days), real Firestore timestamp; `ensure_firestore_ttl` and `ensure_delete_protection` in `scripts/cloudrun_lib.sh`, wired into `scripts/deploy_cloudrun.sh`; `scripts/backfill_job_expiry.py` (dry run by default, `--apply`); `all_jobs()` on the stores | #203 |
| Recovery | `gateway/recovery.py` (`sweep_stale`, `finish_run`): `running` older than `PIPELINE_STALE_SECONDS` (default 1200 s) becomes `failed`, never re-run automatically; `POST /sweep` on the private worker; Luigi-only Telegram `/sweep`; `/pending` lists running jobs; Cloud Scheduler job `sweep-stuck-jobs` every 10 minutes | #204 |
| Privacy | `gateway/privacy.py`: short notice on `/start`, full Italian notice on `/privacy`; optional `PRIVACY_CONTACT`; `process/runbook_privacy_requests.md` | #202 |
| Bookkeeping | learning-loop counters, wiki row, shared Google credentials docs | #205 |

Verified live on 2026-10-09 (project `aistudio-milano`): delete protection `DELETE_PROTECTION_ENABLED`;
TTL on `jobs.expire_at` `ACTIVE`; Scheduler job ENABLED, called the worker at 15:10, 15:20 and 15:30 UTC
with HTTP 200; the worker answers 403 to unauthenticated `POST /sweep` and `/run`. Backfill applied by
Luigi: all 10 existing jobs carry a Firestore timestamp `expire_at` 89 days ahead (approved 2,
classified 4, delivered 2, needs_review 2; none expired). Cloud Logging default bucket retention is
30 days; Firestore point-in-time recovery is disabled. The gateway deploy with the privacy notice was
launched by Luigi with the generic controller text; the live text is still to be confirmed.
Full suite: 818 passed on main after the merges; the 13 failures predate this work and are unchanged.

## Defects found by review and fixed before merging

1. Backfill would have deleted pending jobs: finished jobs now get creation + retention, pending jobs
   get now + retention.
2. A failing `describe` aborted the deploy silently; a `grep -q` + pipefail SIGPIPE hazard; private
   `_collection()` use.
3. A stale-listing race could fail a fresh run after Riprova: the state is re-checked before the
   transition (narrowed, not fully atomic).
4. A bad scheduler location would have aborted the deploy; it is now a warning.
5. Privacy wording: retention text, copies in Luigi's chat and mailbox, log lines cannot be deleted one
   by one, automated-decision wording, `/start` wording.

## Open / for Luigi

- Controller identity (name or company, address, VAT/tax code) and `PRIVACY_CONTACT` not provided yet.
- Transfer-safeguards wording to confirm with a professional; age limit not decided; accept the Google
  Cloud and OpenAI DPAs.
- The notice's "90 days" is true only now that the TTL is active and the backfill has run.
- A job still unfinished at day 90 is deleted.
- A late result dropped after Riprova is only logged.
- The stale threshold (1200 s) may need tuning.
- `/cancella` and refusing fraudulent requests are the next piece (registered separately).
