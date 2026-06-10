#!/usr/bin/env bash
# deploy_gcr.sh — Deploy RAG API to Google Cloud Run
#
# Prerequisites (run once, Luigi):
#   gcloud auth login && gcloud auth application-default login
#   gcloud projects create $PROJECT_ID --name="ai-studio-rag"
#   gcloud billing projects link $PROJECT_ID --billing-account=BILLING_ACCOUNT_ID
#   gcloud services enable run.googleapis.com artifactregistry.googleapis.com \
#       cloudbuild.googleapis.com secretmanager.googleapis.com \
#       --project $PROJECT_ID
#   gcloud artifacts repositories create rag-api-repo \
#       --repository-format=docker --location=europe-west1 --project $PROJECT_ID
#   # Store secrets:
#   echo -n "sk-..." | gcloud secrets create OPENAI_API_KEY --data-file=- --project $PROJECT_ID
#   echo -n "..." | gcloud secrets create TELEGRAM_RAG_BOT_TOKEN --data-file=- --project $PROJECT_ID
#   echo -n "..." | gcloud secrets create TWILIO_AUTH_TOKEN --data-file=- --project $PROJECT_ID
#   echo -n "..." | gcloud secrets create TWILIO_ACCOUNT_SID --data-file=- --project $PROJECT_ID
#   echo -n "..." | gcloud secrets create TWILIO_WHATSAPP_FROM --data-file=- --project $PROJECT_ID

set -euo pipefail

PROJECT_ID="${GCP_PROJECT_ID:-YOUR_PROJECT_ID}"
REGION="${GCP_REGION:-europe-west1}"
SERVICE="rag-api"
REPO="rag-api-repo"
IMAGE="${REGION}-docker.pkg.dev/${PROJECT_ID}/${REPO}/${SERVICE}"
TAG="${IMAGE}:$(git rev-parse --short HEAD)"

REPO_ROOT="$(git rev-parse --show-toplevel)"

echo "==> Building Docker image: ${TAG}"
docker build \
  -f "${REPO_ROOT}/scripts/rag/Dockerfile" \
  -t "${TAG}" \
  "${REPO_ROOT}"

echo "==> Pushing to Artifact Registry"
gcloud auth configure-docker "${REGION}-docker.pkg.dev" --quiet
docker push "${TAG}"

echo "==> Deploying to Cloud Run (${REGION})"
gcloud run deploy "${SERVICE}" \
  --image "${TAG}" \
  --region "${REGION}" \
  --project "${PROJECT_ID}" \
  --platform managed \
  --allow-unauthenticated \
  --port 8000 \
  --memory 1Gi \
  --cpu 1 \
  --min-instances 0 \
  --max-instances 5 \
  --timeout 60 \
  --set-secrets "OPENAI_API_KEY=OPENAI_API_KEY:latest,TELEGRAM_RAG_BOT_TOKEN=TELEGRAM_RAG_BOT_TOKEN:latest,TWILIO_AUTH_TOKEN=TWILIO_AUTH_TOKEN:latest,TWILIO_ACCOUNT_SID=TWILIO_ACCOUNT_SID:latest,TWILIO_WHATSAPP_FROM=TWILIO_WHATSAPP_FROM:latest"

SERVICE_URL=$(gcloud run services describe "${SERVICE}" \
  --region "${REGION}" --project "${PROJECT_ID}" \
  --format "value(status.url)")

echo ""
echo "==> Deployed: ${SERVICE_URL}"
echo "    Health:   ${SERVICE_URL}/health"
echo ""
echo "==> Update Telegram webhook:"
echo "    TELEGRAM_RAG_BOT_TOKEN=... RAG_API_URL=${SERVICE_URL} \\"
echo "    python scripts/rag/register_telegram_webhook.py"
echo ""
echo "==> Update Twilio WhatsApp webhook in console.twilio.com:"
echo "    ${SERVICE_URL}/webhook/whatsapp"
