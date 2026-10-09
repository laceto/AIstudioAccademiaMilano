---
request_id: "036"
date: "2026-10-09"
intent: internal_infra_build
product_type: gateway_approval_pipeline
outcome: success
price: "0.00"
invoice_id: "—"
agents_invoked:
  - name: Claude
    role: scoping_implementation_docs
    action: >
      Five phases, test first, one branch and PR each: (1) Telegram + e-mail notification when a
      job needs review; (2) persistent JobStore (file + Firestore); (3) approve / reject / set
      price from Telegram buttons and commands, Luigi's numeric id only, decided once; (4) not
      done; (5) approved jobs run the LangGraph studio pipeline on a private Cloud Run worker
      through Cloud Tasks, the result goes to Luigi first (Invia al cliente / Scarta).
      Also: per-session conversation log, deploy script hardening, region and cost review.
    duration_sec: 0
    status: ok
  - name: Luigi
    role: operator_and_approver
    action: >
      Chose the design (Firestore, approvals by Telegram, only approved jobs run, Cloud Tasks +
      private worker, review before the customer), ran every deploy (the agent session is blocked
      from creating secrets and public services), rotated the bot tokens after both log leaks,
      and ran the live tests.
    duration_sec: 0
    status: ok
skills_used:
  - breakdown
  - agentic-router
  - langgraph-fundamentals
  - deep-agents-core
  - langgraph-persistence
learning_flags:
  new_skills: []
  new_mcp: []
  risk_score: 3
---

# Request 036 — Approval flow and asynchronous pipeline worker

Internal tooling, no customer price (0.00). Deliverable folder:
`deliverables/2026-10-09_036_approval-pipeline-worker/`. Plan and status:
`docs/plans/luigi-approval-notifications.md`. Operations: `docs/cloud-run-setup.md`.

## Outcome

A request outside the catalogue no longer dies in a log line. The gateway tells Luigi (Telegram with
buttons, plus e-mail to a list), Luigi decides in Telegram, the approved job is queued in Cloud Tasks,
a private Cloud Run worker runs the 6-agent pipeline at the price he chose, and he reviews the file
before the customer gets it.

| Phase | What | PR |
|-------|------|----|
| 1 | `gateway/notify.py`: Telegram (plain text) + e-mail list, isolated channels, deduplicated, rate limited | #188 |
| 2 | `gateway/jobstore.py`: file and Firestore backends, atomic `transition()` | #190 |
| 3 | `gateway/admin.py`, `gateway/admin_telegram.py`: buttons, `/pending /approve /prezzo /reject`, webhook secret token | #193 |
| 5 (1/3) | `gateway/studio_runner.py`: pipeline without git/mail/disk, Marco honours the approved price | #194 |
| 5 (2/3) | `gateway/pipeline_queue.py`, `gateway/pipeline_worker.py`, `Dockerfile.worker`, queue `max-attempts=1` | #195 |
| 5 (3/3) | Invia al cliente / Scarta, `/file`, `/run` | #196 |
| fixes | Cloud Tasks region (#197), `httpx` token logging in worker and RAG API (#198) | |
| support | conversation log (#183), deploy script idempotence (#192), region and cost docs (#191) | |

Verified live on 2026-10-09: jobs `0baa44db93` (approved at 5.50 by price reply), `1a194c1a8b` and
`6249e90eb4` (free approval, pipeline in about 12 s, file reviewed and delivered). RAG bot answers.
Full suite: 671 passed; the 13 failures predate this work and are unchanged.

## Defects found and fixed on the way

1. **Bot token written to Cloud Logging** (twice): `httpx` logs request URLs at INFO and the Bot API
   carries the token in the URL. First in the gateway (07:56), then in the worker (11:18) and the RAG API
   (08:00). All tokens in those lines were revoked; a test now imports every Telegram-facing module in a
   fresh interpreter and requires `httpx` at WARNING.
2. **Forgeable admin identity**: Luigi is recognised by the numeric id inside the webhook payload, which
   anyone can send. The webhook now requires Telegram's secret token header; admin features stay off
   without it.
3. **Pipeline strategies broken in production**: the invoice and landing-page prompts had unescaped
   JSON braces, so those requests failed every time ("missing variables").
4. **Approved risk escalation looped** back to Gianni instead of continuing to QA.
5. **Git Bash rewrote `/tmp/queue`** into a Windows path before it reached `gcloud`; the variable is no
   longer passed.
6. **Secret versions grew on every deploy**; they are added only when the value changes.
7. **Cloud Tasks does not exist in `europe-west8`**: the queue lives in `europe-west6`.

## Not done, on purpose or still open

- Phase 4: refuse fraudulent requests explicitly (today "ricetta medica falsa" goes to review like any
  out-of-catalogue request).
- Firestore: TTL on job documents (they hold user text) and delete protection are not set.
- Privacy notice in the `/start` message; log retention (30 days by default) for stored user text.
- A job stuck in `running` (worker crashed mid-run) is not recovered automatically; `/pending` does not
  list it.
- The cloud worker does not `git push`, send Francesca's e-mail or write `process/audit/`: registering a
  delivery stays manual (this file).
- Customers outside Telegram get no automatic delivery.
- ISS-021 stays open: Telegram is live; WhatsApp and the Streamlit form are not.
- Payments (ISS-011) do not exist; that is why only Luigi-approved jobs run.
