---
request_id: "031"
date: "2026-06-10"
intent: internal_infra_build
product_type: internal_infra_build
outcome: success
price: "€0.00"
invoice_id: "—"
agents_invoked:
  - name: Stacy
    role: intent_classifier
    action: Classified as internal_infra_build — no pricing block; not unknown_product
    duration_sec: 2
    status: ok
  - name: Gianni
    role: technical_scoper
    action: "Scoped GCR migration: deploy_gcr.sh + rag-deploy-gcr.yml workflow; Railway deprecated"
    duration_sec: 5
    status: ok
  - name: Chiara
    role: implementer
    action: "Created scripts/rag/deploy_gcr.sh, .github/workflows/rag-deploy-gcr.yml; deprecated railway.toml"
    duration_sec: 90
    status: ok
  - name: Stacy QA
    role: output_validator
    action: "QA passed — no secrets in code, Workload Identity Federation used (no service account key), HMAC still active on /webhook/whatsapp"
    duration_sec: 5
    status: ok
  - name: Marco
    role: transaction_manager
    action: Internal tooling confirmed; €0.00 per rule 5; actuarial check clean
    duration_sec: 3
    status: ok
  - name: Francesca
    role: delivery
    action: Committed and pushed to claude/railway-gcr-choice-ggbt6t
    duration_sec: 10
    status: ok
skills_used:
  - google_cloud_run_deploy
  - artifact_registry_docker
  - google_secret_manager
  - github_actions_workload_identity
  - dockerfile_authoring
delivery:
  method: github
  branch: claude/railway-gcr-choice-ggbt6t
  files:
    - scripts/rag/deploy_gcr.sh
    - .github/workflows/rag-deploy-gcr.yml
    - railway.toml (deprecated comment added)
  confirmed: true
qa_result: pass
payment:
  amount: "€0.00"
  method: internal
  receipt_id: "—"
learning_flags:
  new_skills:
    - github_actions_workload_identity
  new_mcp: []
  risk_score: 1
  cost_overrun: false
  loss_development_flag: false
---

# Internal Infra Build 031 — RAG API Migration: Railway → Google Cloud Run

## Decision rationale

| Factor | Railway | Google Cloud Run |
|--------|---------|-----------------|
| Pricing model | Always-on (min instance charged) | Pay-per-request, scales to zero |
| Docker C deps | Supported | Supported |
| Memory control | Fixed tiers | 256 MiB – 32 GiB, tunable |
| HTTPS endpoint | Auto | Auto |
| WebSocket / SSE | Limited | `--session-affinity` available |
| Free tier | $5/month credit | 180k vCPU-sec/month |
| Secrets | Env vars UI | Secret Manager (versioned, auditable) |
| CI/CD | `railway up` | Workload Identity Federation (no key files) |

**Decision:** GCR preferred for the RAG API due to scale-to-zero cost profile, Secret Manager
integration, and alignment with the studio's containerised deployment lane.

## Delivered artifacts

| Artifact | Purpose |
|----------|---------|
| `scripts/rag/deploy_gcr.sh` | Manual deployment script (build → push → deploy) |
| `.github/workflows/rag-deploy-gcr.yml` | CI/CD: auto-deploys on push to `scripts/rag/**` or `requirements-rag.txt` |
| `railway.toml` | Kept with deprecation comment — do not reuse |

## GCP setup required (Luigi — one-time)

1. `gcloud auth login && gcloud auth application-default login`
2. Create project and enable APIs (see comments in `deploy_gcr.sh`)
3. Create Artifact Registry repo `rag-api-repo` in `europe-west1`
4. Store 5 secrets in Secret Manager: `OPENAI_API_KEY`, `TELEGRAM_RAG_BOT_TOKEN`, `TWILIO_AUTH_TOKEN`, `TWILIO_ACCOUNT_SID`, `TWILIO_WHATSAPP_FROM`
5. Add GitHub Actions secrets: `GCP_PROJECT_ID`, `GCP_WORKLOAD_IDENTITY_PROVIDER`, `GCP_SERVICE_ACCOUNT`
6. Run `bash scripts/rag/deploy_gcr.sh` for first deploy, then CI takes over

## Post-deploy steps

- Re-register Telegram webhook: `python scripts/rag/register_telegram_webhook.py`
- Update Twilio WhatsApp webhook URL in console.twilio.com to `<SERVICE_URL>/webhook/whatsapp`

## Actuarial notes

- E[revenue]: €0.00 (internal tooling)
- E[cost]: Cloud Run free tier covers expected load; overage ~€0.01/1k requests
- Risk: Secrets must be set in Secret Manager before first deploy — deploy will fail otherwise (expected, not a bug)
- P1 flag: N/A
