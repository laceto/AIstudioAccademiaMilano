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
#   ./scripts/deploy_cloudrun.sh --build=gateway,worker   # rebuild only these (rag-api takes ~10 min)
#
# Services: gateway (public webhook), rag-api (public webhook) and pipeline-worker (private:
# only Cloud Tasks may call it) which runs the studio pipeline for jobs Luigi approved.
#
# Prerequisites:
#   - gcloud installed and `gcloud auth login` done
#   - a project selected (`gcloud config set project ...`) with billing linked
#   - .env at the repo root, with two DIFFERENT Telegram bot tokens
#
set -euo pipefail

REGION="${REGION:-europe-west8}"    # Milan (Cloud Run Tier 1). Firestore's location follows this and is permanent
AR_REPO="${AR_REPO:-aistudio}"
REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
ENV_FILE="$REPO_ROOT/.env"

DRY_RUN=false
SKIP_BUILD=false
BUILD_LIST=""   # empty = rebuild every image; --build=a,b rebuilds only those
for arg in "$@"; do
  case "$arg" in
    --dry-run)    DRY_RUN=true ;;
    --skip-build) SKIP_BUILD=true ;;
    --build=*)    BUILD_LIST="${arg#--build=}" ;;
    -h|--help)    sed -n '2,24p' "${BASH_SOURCE[0]}"; exit 0 ;;
    *) echo "Unknown option: $arg" >&2; exit 2 ;;
  esac
done
if [ -n "$BUILD_LIST" ]; then
  for name in ${BUILD_LIST//,/ }; do
    case "$name" in gateway|worker|rag-api) ;; *) echo "Unknown image in --build: $name (gateway, worker, rag-api)" >&2; exit 2 ;; esac
  done
fi

# want_build NAME: should this image be rebuilt on this run?
want_build() {
  $SKIP_BUILD && return 1
  [ -z "$BUILD_LIST" ] && return 0
  [[ ",$BUILD_LIST," == *",$1,"* ]]
}

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

# upsert_secret and gateway_env_vars live in a separate file so they can be tested.
# shellcheck source=cloudrun_lib.sh
source "$(dirname "${BASH_SOURCE[0]}")/cloudrun_lib.sh"

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
  artifactregistry.googleapis.com secretmanager.googleapis.com \
  firestore.googleapis.com cloudtasks.googleapis.com

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
SECRETS=(TELEGRAM_BOT_TOKEN TELEGRAM_RAG_BOT_TOKEN OPENAI_API_KEY ANTHROPIC_API_KEY SMTP_PASSWORD)
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
  else
    upsert_secret "$S" "$VALUE"   # only adds a version when the value changed
  fi
done

# Secret token for the Telegram webhook: Telegram echoes it in a header on every update and the
# gateway refuses updates without it. Without it anyone could forge "Luigi pressed Approve".
if $DRY_RUN; then
  echo "  [dry-run] TELEGRAM_WEBHOOK_SECRET (from .env, else Secret Manager, else generated)"
  WEBHOOK_SECRET="dry-run-placeholder"
else
  WEBHOOK_SECRET="$(resolve_webhook_secret)"
  echo "  TELEGRAM_WEBHOOK_SECRET — ready"
fi
PRESENT_SECRETS+=(TELEGRAM_WEBHOOK_SECRET)

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

# ── Firestore (job store) ────────────────────────────────────────────────────

say "Firestore database for gateway jobs"
if gcloud firestore databases describe --database='(default)' >/dev/null 2>&1; then
  echo "  already exists"
else
  # The location is permanent for the project: it follows REGION (europe-west8 = Milan).
  run gcloud firestore databases create --database='(default)' \
    --location="$REGION" --type=firestore-native
fi
run gcloud projects add-iam-policy-binding "$PROJECT" \
  --member="serviceAccount:$RUNTIME_SA" \
  --role=roles/datastore.user --condition=None --quiet >/dev/null

# ── Pipeline worker: queue and identities ────────────────────────────────────
# Jobs Luigi approves are queued in Cloud Tasks; the queue calls the private pipeline-worker as the
# pipeline-tasks service account (OIDC). The gateway may create tasks and act as that account.

# Cloud Tasks is not offered in every Cloud Run region: Milan (europe-west8) is refused with
# "not a valid location". The queue only carries a job id, so it can live elsewhere in Europe;
# Zurich is the nearest supported region (`gcloud tasks locations list`).
TASKS_LOCATION="${TASKS_LOCATION:-europe-west6}"
QUEUE_NAME="pipeline-runs"
TASKS_SA_NAME="pipeline-tasks"
TASKS_SA="$TASKS_SA_NAME@$PROJECT.iam.gserviceaccount.com"

say "Pipeline queue and service account"
if $DRY_RUN; then
  echo "  [dry-run] service account $TASKS_SA_NAME, queue $QUEUE_NAME ($TASKS_LOCATION, max-attempts=1)"
else
  ensure_service_account "$TASKS_SA_NAME" "$PROJECT" "Cloud Tasks caller for the pipeline worker"
  ensure_tasks_queue "$QUEUE_NAME" "$TASKS_LOCATION"
fi
run gcloud projects add-iam-policy-binding "$PROJECT" \
  --member="serviceAccount:$RUNTIME_SA" \
  --role=roles/cloudtasks.enqueuer --condition=None --quiet >/dev/null
run gcloud iam service-accounts add-iam-policy-binding "$TASKS_SA" \
  --member="serviceAccount:$RUNTIME_SA" \
  --role=roles/iam.serviceAccountUser --quiet >/dev/null

# ── Build ────────────────────────────────────────────────────────────────────

if $SKIP_BUILD; then
  say "Skipping build (--skip-build)"
else
  if want_build gateway; then
    say "Building gateway image"
    run gcloud builds submit "$REPO_ROOT" \
      --config "$REPO_ROOT/deploy/cloudbuild.gateway.yaml" \
      --substitutions "_IMAGE=$IMAGE_BASE/gateway"
  fi

  if want_build worker; then
    say "Building pipeline worker image (langgraph + langchain)"
    run gcloud builds submit "$REPO_ROOT" \
      --config "$REPO_ROOT/deploy/cloudbuild.worker.yaml" \
      --substitutions "_IMAGE=$IMAGE_BASE/pipeline-worker"
  fi

  if want_build rag-api; then
    say "Building RAG API image (slow — faiss + langchain)"
    run gcloud builds submit "$REPO_ROOT" \
      --config "$REPO_ROOT/deploy/cloudbuild.ragapi.yaml" \
      --substitutions "_IMAGE=$IMAGE_BASE/rag-api"
  fi
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

# The pipeline worker: NOT public. Only the pipeline-tasks service account may invoke it, so nobody
# can start a (paid) pipeline run by calling its URL. One request at a time, a long timeout.
say "Deploying pipeline-worker (private)"
run gcloud run deploy pipeline-worker \
  --image "$IMAGE_BASE/pipeline-worker" --region "$REGION" \
  --no-allow-unauthenticated --memory 1Gi --cpu 1 --timeout 900 --concurrency 1 --max-instances 2 \
  --set-env-vars "$(worker_env_vars)" \
  --set-secrets "$(secret_flags TELEGRAM_BOT_TOKEN OPENAI_API_KEY ANTHROPIC_API_KEY)" \
  --quiet

if $DRY_RUN; then
  WORKER_URL="https://pipeline-worker-dry-run.invalid"
else
  WORKER_URL="$(gcloud run services describe pipeline-worker --region "$REGION" --format='value(status.url)')"
  [ -n "$WORKER_URL" ] || die "Could not read the pipeline-worker URL."
fi
run gcloud run services add-iam-policy-binding pipeline-worker --region "$REGION" \
  --member="serviceAccount:$TASKS_SA" --role=roles/run.invoker --quiet >/dev/null

say "Deploying gateway"
run gcloud run deploy gateway \
  --image "$IMAGE_BASE/gateway" --region "$REGION" \
  --allow-unauthenticated --memory 512Mi --timeout 120 \
  --set-env-vars "$(gateway_env_vars "PIPELINE_QUEUE=$QUEUE_NAME" "PIPELINE_WORKER_URL=$WORKER_URL" "TASKS_LOCATION=$TASKS_LOCATION" "TASKS_INVOKER_SA=$TASKS_SA" "PIPELINE_PROJECT=$PROJECT")" \
  --set-secrets "$(secret_flags TELEGRAM_BOT_TOKEN ANTHROPIC_API_KEY OPENAI_API_KEY SMTP_PASSWORD TELEGRAM_WEBHOOK_SECRET)" \
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
register() {  # $1 = token, $2 = base url, $3 = label, $4 = optional secret_token
  local code extra=()
  [ -n "${4:-}" ] && extra=(-d "secret_token=$4")
  code="$(curl -sS -o /tmp/tg_hook.$$ -w '%{http_code}' \
    "https://api.telegram.org/bot$1/setWebhook" \
    -d "url=$2/webhook/telegram" -d "drop_pending_updates=true" "${extra[@]}")"
  if [ "$code" = "200" ] && grep -q '"ok":true' /tmp/tg_hook.$$; then
    echo "  $3 -> $2/webhook/telegram"
  else
    warn "$3 webhook registration failed (HTTP $code): $(cat /tmp/tg_hook.$$)"
  fi
  rm -f /tmp/tg_hook.$$
}
register "$PIPELINE_TOKEN" "$GW_URL"  "pipeline bot" "$WEBHOOK_SECRET"
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

  gateway          $GW_URL
  rag-api          $RAG_URL
  pipeline-worker  $WORKER_URL   (private)

Test the whole path: send the bot a request outside the catalogue, then on the card press
"Gratis" (or "Imposta prezzo"). You should get "Pipeline avviata per il job ...", and a minute
or two later the finished file with the buttons "Invia al cliente" / "Scarta".

If the pipeline does not start, the gateway tells you why and /run <job_id> retries it.

Logs:
  gcloud run services logs read gateway --region $REGION --limit 50
  gcloud run services logs read pipeline-worker --region $REGION --limit 50
EOF
