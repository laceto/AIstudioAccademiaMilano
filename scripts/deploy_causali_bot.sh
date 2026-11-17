#!/usr/bin/env bash
#
# deploy_causali_bot.sh — deploy the causali bot (causalibot/app.py) to Cloud Run.
#
# What it sets up, all separate from the gateway and the job store:
#   - Firestore database "causali" (own database, TTL on expire_at, delete protection)
#   - service account causali-bot, whose only data role is datastore.user on that database
#   - Secret Manager: bot token and webhook secret_token
#   - Cloud Run service causali-bot (public only because Telegram must reach it)
#   - Telegram setWebhook with secret_token
#   - read-only access to the database for the account running gcloud (bankanalyst reads from the laptop)
# Idempotent: safe to re-run.
#
# Usage:
#   ./scripts/deploy_causali_bot.sh --dry-run     # print every command, change nothing
#   ./scripts/deploy_causali_bot.sh               # deploy
#   ./scripts/deploy_causali_bot.sh --skip-build  # redeploy without rebuilding the image
#
# Prerequisites:
#   - gcloud installed, `gcloud auth login`, project selected, billing linked
#   - .env with TELEGRAM_CAUSALI_BOT_TOKEN (@BotFather /newbot, then /setjoingroups -> Disable)
#     and CAUSALI_ALLOWED_CHAT_ID (your numeric Telegram id, the same as the admin bot)
#
set -euo pipefail

REGION="${REGION:-europe-west8}"
AR_REPO="${AR_REPO:-aistudio}"
SERVICE="${SERVICE:-causali-bot}"
DATABASE="${DATABASE:-causali}"
REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
ENV_FILE="${ENV_FILE:-$REPO_ROOT/.env}"

DRY_RUN=false
SKIP_BUILD=false
for arg in "$@"; do
  case "$arg" in
    --dry-run)    DRY_RUN=true ;;
    --skip-build) SKIP_BUILD=true ;;
    -h|--help)    sed -n '2,22p' "${BASH_SOURCE[0]}"; exit 0 ;;
    *) echo "Unknown option: $arg" >&2; exit 2 ;;
  esac
done

say()  { printf '\n\033[1m==> %s\033[0m\n' "$*"; }
warn() { printf '\033[33mWARN: %s\033[0m\n' "$*" >&2; }
die()  { printf '\033[31mERROR: %s\033[0m\n' "$*" >&2; exit 1; }
run() {
  if $DRY_RUN; then printf '  [dry-run]'; printf ' %q' "$@"; printf '\n'; else "$@"; fi
}

# Read one value from .env. Tolerates CRLF and surrounding quotes, keeps '=' inside the value.
env_val() {
  sed -n "s/^$1=//p" "$ENV_FILE" 2>/dev/null | head -1 | tr -d '\r' \
    | sed -e 's/^"//' -e 's/"$//' -e "s/^'//" -e "s/'$//"
}

# shellcheck source=cloudrun_lib.sh
source "$(dirname "${BASH_SOURCE[0]}")/cloudrun_lib.sh"

command -v gcloud >/dev/null || die "gcloud not found"
[ -f "$ENV_FILE" ] || die ".env not found at $ENV_FILE"
PROJECT="$(gcloud config get-value project 2>/dev/null)"
[ -n "$PROJECT" ] || die "no project selected: gcloud config set project <id>"

TOKEN="$(env_val TELEGRAM_CAUSALI_BOT_TOKEN)"
CHAT_ID="$(env_val CAUSALI_ALLOWED_CHAT_ID)"
case "$TOKEN" in ""|your-*) die "TELEGRAM_CAUSALI_BOT_TOKEN missing in .env (@BotFather -> /newbot)" ;; esac
[[ "$CHAT_ID" =~ ^-?[0-9]+$ ]] || die "CAUSALI_ALLOWED_CHAT_ID must be a numeric Telegram id (in .env)"
for other in TELEGRAM_BOT_TOKEN TELEGRAM_RAG_BOT_TOKEN TELEGRAM_ADMIN_BOT_TOKEN; do
  [ -n "$TOKEN" ] && [ "$TOKEN" = "$(env_val $other)" ] && die "TELEGRAM_CAUSALI_BOT_TOKEN equals $other: one bot cannot serve two roles"
done

SA_NAME="causali-bot"
SA="$SA_NAME@$PROJECT.iam.gserviceaccount.com"
IMAGE="$REGION-docker.pkg.dev/$PROJECT/$AR_REPO/$SERVICE"
TOKEN_SECRET="TELEGRAM_CAUSALI_BOT_TOKEN"
HOOK_SECRET_NAME="TELEGRAM_CAUSALI_WEBHOOK_SECRET"
DB_RESOURCE="projects/$PROJECT/databases/$DATABASE"
# Roles limited to this database only. The IAM condition keeps the gateway's and the worker's data out of reach.
DB_CONDITION="expression=resource.name == \"$DB_RESOURCE\" || resource.name.startsWith(\"$DB_RESOURCE/\"),title=causali-db-only"

say "Project $PROJECT · region $REGION · database $DATABASE"
$DRY_RUN && echo "  (dry run — nothing will be changed)"

say "Enabling APIs"
run gcloud services enable run.googleapis.com cloudbuild.googleapis.com artifactregistry.googleapis.com \
  secretmanager.googleapis.com firestore.googleapis.com iam.googleapis.com

say "Artifact Registry repository '$AR_REPO'"
if gcloud artifacts repositories describe "$AR_REPO" --location="$REGION" >/dev/null 2>&1; then
  echo "  already exists"
else
  run gcloud artifacts repositories create "$AR_REPO" --repository-format=docker --location="$REGION"
fi

say "Firestore database '$DATABASE' (separate from the job store)"
if $DRY_RUN; then
  echo "  [dry-run] create database $DATABASE in $REGION; TTL on expire_at for causali and bozze; delete protection"
else
  ensure_firestore_database "$DATABASE" "$REGION"
  ensure_firestore_ttl causali expire_at "$DATABASE"   # 24 months after the movement date
  ensure_firestore_ttl bozze expire_at "$DATABASE"     # drafts: one day
  ensure_delete_protection "$DATABASE"
fi

say "Service account $SA_NAME (one data role, on this database only)"
if $DRY_RUN; then
  echo "  [dry-run] ensure service account $SA_NAME"
else
  ensure_service_account "$SA_NAME" "$PROJECT" "causali bot Cloud Run service"
fi
run gcloud projects add-iam-policy-binding "$PROJECT" --member="serviceAccount:$SA" \
  --role=roles/datastore.user --condition="$DB_CONDITION" --quiet --format=none

say "Read-only access to the database for the account running gcloud (bankanalyst reads the causali)"
ME="$(gcloud config get-value account 2>/dev/null || true)"
if [ -n "$ME" ]; then
  run gcloud projects add-iam-policy-binding "$PROJECT" --member="user:$ME" \
    --role=roles/datastore.viewer --condition="$DB_CONDITION" --quiet --format=none
else
  warn "no gcloud account found: grant roles/datastore.viewer on $DATABASE to yourself by hand"
fi

say "Secrets"
if $DRY_RUN; then
  echo "  [dry-run] upsert $TOKEN_SECRET; resolve $HOOK_SECRET_NAME"
  HOOK_SECRET="dry-run-secret"
else
  upsert_secret "$TOKEN_SECRET" "$TOKEN"
  HOOK_SECRET="$(resolve_secret "$HOOK_SECRET_NAME")"
fi
for s in "$TOKEN_SECRET" "$HOOK_SECRET_NAME"; do
  run gcloud secrets add-iam-policy-binding "$s" --member="serviceAccount:$SA" \
    --role=roles/secretmanager.secretAccessor --quiet --format=none
done

if $SKIP_BUILD; then
  say "Build skipped"
else
  say "Building $IMAGE"
  run gcloud builds submit --config deploy/cloudbuild.causali.yaml --substitutions "_IMAGE=$IMAGE" .
fi

say "Deploying $SERVICE"
# One instance is plenty for one person; it scales to zero, so it costs nothing while unused.
run gcloud run deploy "$SERVICE" --image "$IMAGE" --region "$REGION" \
  --service-account "$SA" --allow-unauthenticated \
  --set-secrets "$TOKEN_SECRET=$TOKEN_SECRET:latest,$HOOK_SECRET_NAME=$HOOK_SECRET_NAME:latest" \
  --set-env-vars "CAUSALI_ALLOWED_CHAT_ID=$CHAT_ID,GOOGLE_CLOUD_PROJECT=$PROJECT" \
  --max-instances 1 --memory 256Mi --cpu 1 --timeout 60 --quiet

if $DRY_RUN; then
  URL="https://$SERVICE-<hash>.$REGION.run.app"
else
  URL="$(gcloud run services describe "$SERVICE" --region "$REGION" --format='value(status.url)')"
fi

say "Registering the Telegram webhook"
if $DRY_RUN; then
  echo "  [dry-run] setWebhook url=$URL/webhook/telegram-causali secret_token=<hidden> drop_pending_updates=true"
else
  code="$(curl -sS -o /tmp/tg_hook.$$ -w '%{http_code}' "https://api.telegram.org/bot$TOKEN/setWebhook" \
    -d "url=$URL/webhook/telegram-causali" -d "drop_pending_updates=true" -d "secret_token=$HOOK_SECRET")"
  if [ "$code" = "200" ] && grep -q '"ok":true' /tmp/tg_hook.$$; then
    echo "  causali bot -> $URL/webhook/telegram-causali"
  else
    warn "webhook registration failed (HTTP $code): $(cat /tmp/tg_hook.$$)"
  fi
  rm -f /tmp/tg_hook.$$
fi

say "Verifying"
if ! $DRY_RUN && command -v python3 >/dev/null; then
  python3 "$REPO_ROOT/scripts/check_telegram.py" --only causali || warn "check_telegram.py reported problems — read them before testing."
fi

say "Done"
cat <<EOF
  1. Open the bot in Telegram, press Start, send:  250 credem pulizie Valeria  (then Salva)
  2. For bankanalyst, once:   gcloud auth application-default login
     and in .env:             CAUSALI_FIRESTORE_PROJECT=$PROJECT
  3. Log:  gcloud logging read 'resource.labels.service_name="$SERVICE"' --limit 50
EOF
