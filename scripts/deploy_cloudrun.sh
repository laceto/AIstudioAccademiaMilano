#!/usr/bin/env bash
#
# deploy_cloudrun.sh — deploy the Telegram channels to Google Cloud Run.
#
# Runs the whole path from an empty project to two live webhook services:
# enable APIs, create the image repo, push secrets from .env, build both
# images, deploy, wire them together, register the webhooks, verify.
#
# Idempotent: safe to re-run. Existing secrets get a new version, existing
# services are updated in place.
#
# Usage:
#   ./scripts/deploy_cloudrun.sh --dry-run     # print every command, change nothing
#   ./scripts/deploy_cloudrun.sh
#   ./scripts/deploy_cloudrun.sh --skip-build  # redeploy without rebuilding images
#
# Prerequisites:
#   - gcloud installed and `gcloud auth login` done
#   - a project selected (`gcloud config set project ...`) with billing linked
#   - .env at the repo root, with two DIFFERENT Telegram bot tokens
#
set -euo pipefail

REGION="${REGION:-us-central1}"     # free tier applies to select US regions
AR_REPO="${AR_REPO:-aistudio}"
REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
ENV_FILE="$REPO_ROOT/.env"

DRY_RUN=false
SKIP_BUILD=false
for arg in "$@"; do
  case "$arg" in
    --dry-run)    DRY_RUN=true ;;
    --skip-build) SKIP_BUILD=true ;;
    -h|--help)    sed -n '2,20p' "${BASH_SOURCE[0]}"; exit 0 ;;
    *) echo "Unknown option: $arg" >&2; exit 2 ;;
  esac
done

say()  { printf '\n\033[1m==> %s\033[0m\n' "$*"; }
warn() { printf '\033[33mWARN: %s\033[0m\n' "$*" >&2; }
die()  { printf '\033[31mERROR: %s\033[0m\n' "$*" >&2; exit 1; }

run() {
  if $DRY_RUN; then
    printf '  [dry-run]'; printf ' %q' "$@"; printf '\n'
  else
    "$@"
  fi
}

# Read one value from .env. Tolerates CRLF (the repo is edited on Windows too)
# and surrounding quotes, and keeps '=' inside the value.
env_val() {
  sed -n "s/^$1=//p" "$ENV_FILE" 2>/dev/null | head -1 | tr -d '\r' \
    | sed -e 's/^"//' -e 's/"$//' -e "s/^'//" -e "s/'$//"
}

# ── Preconditions ────────────────────────────────────────────────────────────

command -v gcloud >/dev/null || die "gcloud not found — install the Google Cloud CLI first."
[ -f "$ENV_FILE" ] || die ".env not found at $ENV_FILE — copy .env.example and fill it in."

PROJECT="$(gcloud config get-value project 2>/dev/null || true)"
[ -n "$PROJECT" ] && [ "$PROJECT" != "(unset)" ] \
  || die "No project selected. Run: gcloud config set project YOUR_PROJECT_ID"

gcloud auth list --filter=status:ACTIVE --format='value(account)' | grep -q . \
  || die "Not authenticated. Run: gcloud auth login"

PIPELINE_TOKEN="$(env_val TELEGRAM_BOT_TOKEN)"
RAG_TOKEN="$(env_val TELEGRAM_RAG_BOT_TOKEN)"

[ -n "$PIPELINE_TOKEN" ] || die "TELEGRAM_BOT_TOKEN missing from .env"
[ -n "$RAG_TOKEN" ]      || die "TELEGRAM_RAG_BOT_TOKEN missing from .env"
[ "$PIPELINE_TOKEN" != "$RAG_TOKEN" ] || die \
  "TELEGRAM_BOT_TOKEN and TELEGRAM_RAG_BOT_TOKEN are the same token.
       One bot cannot serve both services — whichever registers its webhook last
       silently wins and the other goes dead. Create a second bot via @BotFather."

IMAGE_BASE="$REGION-docker.pkg.dev/$PROJECT/$AR_REPO"

say "Project $PROJECT · region $REGION"
$DRY_RUN && echo "  (dry run — nothing will be changed)"

# ── APIs and image repository ────────────────────────────────────────────────

say "Enabling APIs"
run gcloud services enable \
  run.googleapis.com cloudbuild.googleapis.com \
  artifactregistry.googleapis.com secretmanager.googleapis.com

say "Artifact Registry repository '$AR_REPO'"
if gcloud artifacts repositories describe "$AR_REPO" --location="$REGION" >/dev/null 2>&1; then
  echo "  already exists"
else
  run gcloud artifacts repositories create "$AR_REPO" \
    --repository-format=docker --location="$REGION" \
    --description="AI Studio Telegram gateway images"
fi

# ── Secrets ──────────────────────────────────────────────────────────────────

say "Secrets from .env"
SECRETS=(TELEGRAM_BOT_TOKEN TELEGRAM_RAG_BOT_TOKEN OPENAI_API_KEY ANTHROPIC_API_KEY)
PRESENT_SECRETS=()

for S in "${SECRETS[@]}"; do
  VALUE="$(env_val "$S")"
  # .env.example placeholders take several shapes: your-bot-token-here,
  # sk-proj-YOUR_KEY_HERE, sk-ant-your-key-here. Catch all of them.
  if [ -z "$VALUE" ] || [[ "${VALUE,,}" =~ (^your-|your_key_here|your-key-here|-your-) ]]; then
    warn "$S looks unset or is still a placeholder in .env — skipping"
    continue
  fi
  PRESENT_SECRETS+=("$S")
  if $DRY_RUN; then
    echo "  [dry-run] store $S (${#VALUE} chars)"
  elif gcloud secrets describe "$S" >/dev/null 2>&1; then
    printf '%s' "$VALUE" | gcloud secrets versions add "$S" --data-file=- >/dev/null
    echo "  $S — new version"
  else
    printf '%s' "$VALUE" | gcloud secrets create "$S" --data-file=- --replication-policy=automatic >/dev/null
    echo "  $S — created"
  fi
done

printf '%s\n' "${PRESENT_SECRETS[@]}" | grep -qx TELEGRAM_BOT_TOKEN \
  || die "TELEGRAM_BOT_TOKEN did not make it into Secret Manager."
if ! printf '%s\n' "${PRESENT_SECRETS[@]}" | grep -qxE 'ANTHROPIC_API_KEY|OPENAI_API_KEY'; then
  die "Neither ANTHROPIC_API_KEY nor OPENAI_API_KEY is set — the worker cannot classify."
fi

say "Granting the runtime service account read access"
PROJECT_NUMBER="$(gcloud projects describe "$PROJECT" --format='value(projectNumber)')"
RUNTIME_SA="${PROJECT_NUMBER}-compute@developer.gserviceaccount.com"
for S in "${PRESENT_SECRETS[@]}"; do
  run gcloud secrets add-iam-policy-binding "$S" \
    --member="serviceAccount:$RUNTIME_SA" \
    --role=roles/secretmanager.secretAccessor --quiet >/dev/null
done
echo "  $RUNTIME_SA"

# ── Build ────────────────────────────────────────────────────────────────────

if $SKIP_BUILD; then
  say "Skipping build (--skip-build)"
else
  say "Building gateway image"
  run gcloud builds submit "$REPO_ROOT" \
    --config "$REPO_ROOT/deploy/cloudbuild.gateway.yaml" \
    --substitutions "_IMAGE=$IMAGE_BASE/gateway"

  say "Building RAG API image (slow — faiss + langchain)"
  run gcloud builds submit "$REPO_ROOT" \
    --config "$REPO_ROOT/deploy/cloudbuild.ragapi.yaml" \
    --substitutions "_IMAGE=$IMAGE_BASE/rag-api"
fi

# ── Deploy ───────────────────────────────────────────────────────────────────

secret_flags() {  # only wire secrets that actually exist
  local out=()
  for S in "$@"; do
    printf '%s\n' "${PRESENT_SECRETS[@]}" | grep -qx "$S" && out+=("$S=$S:latest")
  done
  IFS=,; echo "${out[*]}"
}

say "Deploying rag-api"
run gcloud run deploy rag-api \
  --image "$IMAGE_BASE/rag-api" --region "$REGION" \
  --allow-unauthenticated --memory 2Gi --cpu 2 --timeout 300 --cpu-boost \
  --set-secrets "$(secret_flags TELEGRAM_RAG_BOT_TOKEN OPENAI_API_KEY)" \
  --quiet

say "Deploying gateway"
run gcloud run deploy gateway \
  --image "$IMAGE_BASE/gateway" --region "$REGION" \
  --allow-unauthenticated --memory 512Mi --timeout 120 \
  --set-env-vars "GATEWAY_SYNC_REPLY=1,GATEWAY_QUEUE_DIR=/tmp/queue" \
  --set-secrets "$(secret_flags TELEGRAM_BOT_TOKEN ANTHROPIC_API_KEY OPENAI_API_KEY)" \
  --quiet

if $DRY_RUN; then
  say "Dry run complete — nothing was changed."
  exit 0
fi

RAG_URL="$(gcloud run services describe rag-api --region "$REGION" --format='value(status.url)')"
GW_URL="$(gcloud run services describe gateway  --region "$REGION" --format='value(status.url)')"
[ -n "$RAG_URL" ] && [ -n "$GW_URL" ] || die "Could not read the deployed service URLs."

say "Pointing the gateway's /ask proxy at the RAG service"
gcloud run services update gateway --region "$REGION" \
  --update-env-vars "RAG_API_URL=$RAG_URL" --quiet >/dev/null

# ── Webhooks ─────────────────────────────────────────────────────────────────

say "Registering Telegram webhooks"
register() {  # $1 = token, $2 = base url, $3 = label
  local code
  code="$(curl -sS -o /tmp/tg_hook.$$ -w '%{http_code}' \
    "https://api.telegram.org/bot$1/setWebhook" \
    -d "url=$2/webhook/telegram" -d "drop_pending_updates=true")"
  if [ "$code" = "200" ] && grep -q '"ok":true' /tmp/tg_hook.$$; then
    echo "  $3 -> $2/webhook/telegram"
  else
    warn "$3 webhook registration failed (HTTP $code): $(cat /tmp/tg_hook.$$)"
  fi
  rm -f /tmp/tg_hook.$$
}
register "$PIPELINE_TOKEN" "$GW_URL"  "pipeline bot"
register "$RAG_TOKEN"      "$RAG_URL" "RAG bot"

# ── Verify ───────────────────────────────────────────────────────────────────

say "Verifying"
if command -v python3 >/dev/null; then
  python3 "$REPO_ROOT/scripts/check_telegram.py" --expect-webhook pipeline || \
    warn "check_telegram.py reported problems — read them before testing."
else
  warn "python3 not found — run scripts/check_telegram.py yourself."
fi

cat <<EOF

Done.

  gateway   $GW_URL
  rag-api   $RAG_URL

Test: message the pipeline bot "Ho bisogno di una landing page per il mio ristorante".
You should get ONE reply naming the product and EUR 9.90. If you get a Job ID and
then silence, GATEWAY_SYNC_REPLY did not reach the container:

  gcloud run services describe gateway --region $REGION --format='value(spec.template.spec.containers[0].env)'

Logs:
  gcloud run services logs read gateway --region $REGION --limit 50
EOF
