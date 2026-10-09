---
request_id: "038"
date: "2026-10-09"
intent: internal_infra_build
product_type: erasure_and_refusals
outcome: success
price: "0.00"
invoice_id: "—"
agents_invoked:
  - name: Claude
    role: orchestrator
    action: >
      Briefed three engineers working in parallel in isolated git worktrees (erase on request,
      refuse fraudulent requests, official registration of delivery 037), commissioned independent
      reviews (technical audit of both code PRs, compliance review of the refusal flow), sent the
      findings back for fixes, merged in order, verified live, cleaned up the worktrees and 44
      local branches created in the session. Also fixed /privacy overflowing Telegram's limit
      (PR #209) and the learning loop's broken hook promotion (PR #211).
    duration_sec: 0
    status: ok
  - name: Chiara
    role: engineers
    action: >
      Three implementers, one per task: /cancella with confirmation card and erasure record
      (PR #207); refusal of clearly illegal requests with a deterministic phrase filter, a model
      flag, RIESAMINA for the customer and Riesamina for the owner (PR #208); registration of 037
      (PR #206).
    duration_sec: 0
    status: ok
  - name: Technical Auditor
    role: reviewer
    action: >
      Reviewed #207 (two blockers: a partial failure left deletions unrecorded; the result message
      could exceed Telegram's 4096 characters) and #208 (refusals could starve the review notice
      through a shared rate window; 24 of 87 benign requests were refused by the phrase filter;
      a comma let an educational word shield an illegal phrase). All fixed before merge.
    duration_sec: 0
    status: ok
  - name: Compliance Agent
    role: reviewer
    action: >
      Reviewed #208: the notice promised a human review the customer could not request; the refusal
      counter and the category label were not disclosed; refused text kept 90 days; reexamined requests
      would have been e-mailed. All addressed (RIESAMINA, wording, 30-day retention, Telegram-only,
      possible_* labels).
    duration_sec: 0
    status: ok
  - name: Luigi
    role: operator_and_approver
    action: >
      Asked for the team, chose to fix the learning-loop generator, deployed, and ran the live tests
      (/privacy, a fraudulent request, RIESAMINA, /cancella).
    duration_sec: 0
    status: ok
skills_used:
  - breakdown
learning_flags:
  new_skills: []
  new_mcp: []
  risk_score: 3
---

# Request 038 — Erase on request and refusal of fraudulent requests

Internal tooling, no customer price (0.00). Deliverable folder:
`deliverables/2026-10-09_038_erasure-and-refusals/`. Operations: `docs/cloud-run-setup.md` (commands table and
section 1f), `process/runbook_privacy_requests.md`. Plan: `docs/plans/luigi-approval-notifications.md` (Phase 4 done).

Risk score 3: an irreversible deletion in production, and an automatic refusal whose legal wording
(art. 22, legitimate interest) a professional still has to confirm.

## Outcome

| Item | PR |
|------|----|
| `/cancella <job_id>` and `/cancella chat <chat_id>`: confirmation card (counts, statuses, dates, never the customer's text), Conferma / Annulla, refuses `running`/`delivering` jobs, erases exactly what the card showed, durable record in `erasures` | #207 |
| Refusal of clearly illegal requests: phrase filter `gateway/safety.py` (runs before the model, needs no API key) plus the model's `refuse` flag; neutral reply; owner notice with a counter and Riesamina; customer can reply RIESAMINA; refused jobs kept 30 days; reexamined jobs go to Telegram only | #208 |
| `/privacy` sent as several messages (it was 32 characters under Telegram's limit) | #209 |
| Learning loop: a skill becomes a hook only if `scripts/preload_<skill>.py` exists, portable command, no fake `risk_score` | #211 |
| Registration of 037, learning-loop counters and curated wiki rows | #206, #205, #210 |

Verified live on 2026-10-09 after the deploy (gateway 00022, worker 00006):
- `/privacy` arrived as two messages.
- "ricetta medica falsa" was refused by the phrase filter alone (`refused_by: safety_backstop`, no model call),
  category `possible_fake_document`, `expire_at` 30 days ahead, the owner was notified.
- RIESAMINA from the customer created no job, set `review_requested_at`, answered the customer.
- `/cancella` with a mistyped id answered "non trovato"; with the right id it showed the card, deleted the job,
  wrote one record (`at`, `by`, `count`, `job_ids`, `scope`; no chat id, no text) and listed the manual steps.
- Independent check of the phrase filter: 0 of 39 ordinary requests refused, 12 of 14 illegal ones caught.
- No new Telegram token in any log. Full suite 1042 passed; the 13 failures predate this work.

## Not done, on purpose or still open

- Controller identity (name or company, address, tax code) and `PRIVACY_CONTACT` are still the generic text.
- A professional should confirm: legal basis, safeguards for transfers outside the EU, the legitimate-interest
  balancing for the refusal counter, the art. 22 assessment, and whether suspected crime would ever be reported.
- The phrase filter misses "certificato di malattia falso" and "forge a doctor's signature"; paraphrases, typos,
  other languages and split messages get past it. The model flag is the second layer; Riesamina undoes false positives.
  Keyloggers and phishing-page requests are refused on purpose (dual use).
- `erasures` has no TTL (accountability); erasing does not reach the owner's mailbox, his Telegram chat or the
  30-day Cloud Logging lines, which the bot lists as manual steps.
- The check-then-delete in `/cancella` is not atomic: in the rare case a worker claims an `approved` job in
  between, the run ends as "lost". Documented in the runbook.
- Not confirmed from the logs: that the owner received the "il cliente chiede il riesame" message (only failures
  are logged), button rendering in the real Telegram client, and the model-based refusal path on a real model.
- Two skill-preload hooks promoted by the old learning loop were deliberately left out (see #211).
