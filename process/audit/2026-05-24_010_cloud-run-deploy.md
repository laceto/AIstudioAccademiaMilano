---
request_id: "010"
date: "2026-05-24"
intent: chatbot_creation
intent_subtype: deploy_existing_app_new_platform
product_sku: chatbot_app
price: 19.90
currency: EUR
outcome: success
agents_invoked:
  - {name: Stacy, role: intent_classification, action: unknown_product escalated to Luigi — price approved EUR 19.90, duration_sec: 38, status: pass}
  - {name: Gianni, role: technical_scoping, action: full GCP setup spec (Dockerfile + deploy.sh + Secret Manager), duration_sec: 78, status: pass}
  - {name: Chiara, role: implementation, action: Dockerfile + .dockerignore + deploy.sh + requirements.txt, duration_sec: 193, status: pass}
  - {name: Stacy, role: qa_validation, action: FAIL then PASS after kitai requirements.txt regression fixed, duration_sec: 41, status: pass}
  - {name: Marco, role: financial_processing, action: INV-010 EUR 19.90 approved 97.6% margin, duration_sec: 45, status: pass}
  - {name: Francesca, role: delivery, action: git push origin main (laceto/rss_feed) + audit log, duration_sec: 12, status: pass}
skills_used:
  - google_cloud_run_deploy
  - artifact_registry_docker
  - google_secret_manager
  - cloud_build_submit
  - dockerfile_authoring
learning_flags:
  new_skills:
    - google_cloud_run_deploy
    - artifact_registry_docker
    - google_secret_manager
    - cloud_build_submit
    - dockerfile_authoring
  new_mcp: []
  risk_score: 1
notes: |
  Stacy QA caught requirements.txt regression: kitai HTTPS URL must stay for
  Streamlit Cloud compat. Docker pip install skips it (wheel pre-installed).
  GCP project does not exist yet — Luigi must run Section A steps in deploy.sh
  README before executing deploy.sh.
  Cloud Run free tier: 180k vCPU-sec/month. Monitor at console.cloud.google.com.
---

# Request 010 — Google Cloud Run Deployment

Deploy `output/chatbot_rag.py` from `laceto/rss_feed` to Google Cloud Run.

## Delivered artifacts

| Artifact | Location | Status |
|---|---|---|
| `Dockerfile` | `laceto/rss_feed` root | Committed + pushed |
| `.dockerignore` | `laceto/rss_feed` root | Committed + pushed |
| `deploy.sh` | `laceto/rss_feed` root | Committed + pushed (chmod 755) |
| `requirements.txt` | `laceto/rss_feed` root | Fixed (kitai URL restored) |

## GCP setup required (Luigi — before running deploy.sh)

1. `gcloud auth login && gcloud auth application-default login`
2. `gcloud projects create YOUR_PROJECT_ID --name="ai-studio-rss-feed"`
3. `gcloud billing projects link YOUR_PROJECT_ID --billing-account=BILLING_ACCOUNT_ID`
4. Enable APIs: `run.googleapis.com artifactregistry.googleapis.com cloudbuild.googleapis.com secretmanager.googleapis.com`
5. Create Artifact Registry repo: `gcloud artifacts repositories create rss-feed-repo --repository-format=docker --location=us-central1`
6. Create service account `rss-feed-runner` with roles: `run.admin`, `artifactregistry.writer`, `secretmanager.secretAccessor`
7. Store key: `echo -n "sk-..." | gcloud secrets create OPENAI_API_KEY --data-file=- --replication-policy=automatic`
8. Edit `PROJECT_ID` in `deploy.sh`, then `bash deploy.sh`

## Invoice

INV-010 | EUR 19.90 | 2026-05-24
