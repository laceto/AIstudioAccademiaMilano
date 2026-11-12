---
request_id: "035"
date: "2026-10-09"
intent: agent_deploy_streamlit
product_type: cloud_run_hosting
outcome: success
price: "0.00"
invoice_id: "—"
agents_invoked:
  - name: Claude
    role: scoping_and_docs
    action: >
      Mapped existing Dockerfiles, found scripts/deploy_cloudrun.sh and the runbook,
      verified the script with --dry-run, wrote docs/cloud-run-setup.md, switched the
      default region to europe-west8, fixed the cp1252 crash in check_telegram.py (TDD).
    duration_sec: 0
    status: ok
  - name: Luigi
    role: operator
    action: >
      Linked billing account, ran scripts/deploy_cloudrun.sh (agent session was blocked
      from creating secrets and public services by the permission system).
    duration_sec: 0
    status: ok
skills_used: [breakdown]
learning_flags:
  new_skills: []
  new_mcp: []
  risk_score: 2
---

# Request 035 — Cloud Run deploy (gateway + rag-api)

Internal tooling, no customer price (0.00).

## Outcome

- Project `aistudio-milano`, billing `016BA2-DDA96E-2DDB46` linked, APIs enabled.
- Images built (gateway 1m57s, rag-api 9m28s) into Artifact Registry `aistudio` (`europe-west8`).
- `gateway` and `rag-api` live; `/docs` returns 200 on both.
- Telegram webhooks registered for both bots, 0 pending updates, check_telegram: healthy.

## Findings

- `GATEWAY_HMAC_SECRET` is not needed: `verify_hmac()` is defined but no endpoint calls it.
- `scripts/check_telegram.py` crashed on Windows consoles (cp1252); fixed with `_ensure_utf8()`
  plus a regression test.
- Region default moved from `us-central1` to `europe-west8`. The always-free tier only
  covers select US regions, so small charges are possible; a budget alert is advisable.

## Open follow-ups

- End-to-end Telegram test by Luigi (landing-page message should answer once with EUR 9.90).
- Persistent job storage (Firestore / Cloud SQL): `GET /status/{job_id}` 404s after instance loss.
- GitHub Actions deploy workflow (Workload Identity Federation).
- WhatsApp channel and Streamlit form on Cloud Run (ISS-021 stays OPEN).
- Budget alert in Google Cloud Billing.
