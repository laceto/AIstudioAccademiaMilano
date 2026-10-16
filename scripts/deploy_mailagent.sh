#!/usr/bin/env bash
#
# deploy_mailagent.sh — deploy the Gmail tidy service (mailagent/server.py) to Cloud Run.
#
# APIs, two service accounts, the Gmail token into Secret Manager, image build, private
# Cloud Run service, Cloud Scheduler job that calls POST /process every hour.
# Idempotent: safe to re-run.
#
# Usage:
#   ./scripts/deploy_mailagent.sh --dry-run     # print every command, change nothing
#   ./scripts/deploy_mailagent.sh               # deploy with MAILAGENT_DRY_RUN=1: reads mail, changes nothing
#   ./scripts/deploy_mailagent.sh --live        # after reading a dry run's log: really file mail
#   ./scripts/deploy_mailagent.sh --skip-build  # redeploy without rebuilding the image
#
# Prerequisites:
#   - gcloud installed, `gcloud auth login`, project selected, billing linked
#   - the account's token file, made once with `python -m mailagent auth gmail-luigi`
#     (TOKEN_FILE=... to point elsewhere). See process/runbook_mailagent_cloudrun.md.
#
set -euo pipefail

REGION="${REGION:-europe-west8}"
AR_REPO="${AR_REPO:-aistudio}"
SERVICE="${SERVICE:-mailagent}"
SCHEDULE="${SCHEDULE:-0 * * * *}"   # UTC; hourly is plenty for newsletters
SCHEDULER_LOCATION="${SCHEDULER_LOCATION:-europe-west6}"   # Scheduler may not offer Milan
TOKEN_SECRET="${TOKEN_SECRET:-MAILAGENT_GMAIL_LUIGI_TOKEN}"  # = options.token_env in config/mailagent_accounts.yaml
TOKEN_FILE="${TOKEN_FILE:-$HOME/.credentials/google/mailagent_gmail-luigi_token.json}"

DRY_RUN=false
SKIP_BUILD=false
LIVE=0
for arg in "$@"; do
  case "$arg" in
    --dry-run)    DRY_RUN=true ;;
    --skip-build) SKIP_BUILD=true ;;
    --live)       LIVE=1 ;;
    -h|--help)    sed -n '2,18p' "${BASH_SOURCE[0]}"; exit 0 ;;
    *) echo "Unknown option: $arg" >&2; exit 2 ;;
  esac
done

say()  { printf '\n\033[1m==> %s\033[0m\n' "$*"; }
warn() { printf '\033[33mWARN: %s\033[0m\n' "$*" >&2; }
die()  { printf '\033[31mERROR: %s\033[0m\n' "$*" >&2; exit 1; }
run() {
  if $DRY_RUN; then printf '  [dry-run]'; printf ' %q' "$@"; printf '\n'; else "$@"; fi
}
env_val() { :; }  # cloudrun_lib.sh expects it; this script reads nothing from .env

# shellcheck source=cloudrun_lib.sh
source "$(dirname "${BASH_SOURCE[0]}")/cloudrun_lib.sh"

command -v gcloud >/dev/null || die "gcloud not found"
PROJECT="$(gcloud config get-value project 2>/dev/null)"
[ -n "$PROJECT" ] || die "no project selected: gcloud config set project <id>"
if [ ! -f "$TOKEN_FILE" ]; then
  msg="token file not found: $TOKEN_FILE (run: python -m mailagent auth gmail-luigi, or set TOKEN_FILE)"
  if $DRY_RUN; then warn "$msg"; else die "$msg"; fi
elif ! grep -q '"refresh_token"' "$TOKEN_FILE"; then
  die "$TOKEN_FILE has no refresh_token: Cloud Run could not renew it"
fi

RUN_SA="mailagent-run@$PROJECT.iam.gserviceaccount.com"        # identity of the service: reads its secret
INVOKER_SA="mailagent-invoker@$PROJECT.iam.gserviceaccount.com" # identity of Cloud Scheduler: may call the service
IMAGE="$REGION-docker.pkg.dev/$PROJECT/$AR_REPO/$SERVICE"

say "Project $PROJECT · region $REGION · MAILAGENT_DRY_RUN=$((1 - LIVE))"
$DRY_RUN && echo "  (dry run — nothing will be changed)"

say "Enabling APIs"
run gcloud services enable gmail.googleapis.com run.googleapis.com cloudbuild.googleapis.com \
  artifactregistry.googleapis.com secretmanager.googleapis.com cloudscheduler.googleapis.com iam.googleapis.com

say "Artifact Registry repository '$AR_REPO'"
if gcloud artifacts repositories describe "$AR_REPO" --location="$REGION" >/dev/null 2>&1; then
  echo "  already exists"
else
  run gcloud artifacts repositories create "$AR_REPO" --repository-format=docker --location="$REGION"
fi

say "Service accounts"
if $DRY_RUN; then
  echo "  [dry-run] ensure mailagent-run, mailagent-invoker"
else
  ensure_service_account mailagent-run "$PROJECT" "mailagent Cloud Run service"
  ensure_service_account mailagent-invoker "$PROJECT" "Cloud Scheduler -> mailagent /process"
fi

say "Gmail token -> Secret Manager ($TOKEN_SECRET)"
if $DRY_RUN; then
  echo "  [dry-run] upsert_secret $TOKEN_SECRET <contents of $TOKEN_FILE>"
else
  upsert_secret "$TOKEN_SECRET" "$(cat "$TOKEN_FILE")"
fi
run gcloud secrets add-iam-policy-binding "$TOKEN_SECRET" \
  --member="serviceAccount:$RUN_SA" --role=roles/secretmanager.secretAccessor --quiet --format=none

if $SKIP_BUILD; then
  say "Build skipped"
else
  say "Building $IMAGE"
  run gcloud builds submit --config deploy/cloudbuild.mailagent.yaml --substitutions "_IMAGE=$IMAGE" .
fi

say "Deploying $SERVICE (private)"
# One instance, one request at a time: two overlapping runs would file the same mail twice (harmless, but noisy).
run gcloud run deploy "$SERVICE" --image "$IMAGE" --region "$REGION" \
  --service-account "$RUN_SA" --no-allow-unauthenticated \
  --set-secrets "$TOKEN_SECRET=$TOKEN_SECRET:latest" \
  --set-env-vars "MAILAGENT_DRY_RUN=$((1 - LIVE))" \
  --max-instances 1 --concurrency 1 --memory 512Mi --cpu 1 --timeout 300

if $DRY_RUN; then
  URL="https://$SERVICE-<hash>.$REGION.run.app"
else
  URL="$(gcloud run services describe "$SERVICE" --region "$REGION" --format='value(status.url)')"
fi
run gcloud run services add-iam-policy-binding "$SERVICE" --region "$REGION" \
  --member="serviceAccount:$INVOKER_SA" --role=roles/run.invoker --quiet --format=none

say "Cloud Scheduler job mailagent-tidy ($SCHEDULE UTC, $SCHEDULER_LOCATION)"
if $DRY_RUN; then
  echo "  [dry-run] scheduler job mailagent-tidy -> POST $URL/process as $INVOKER_SA"
elif ! ensure_scheduler_job mailagent-tidy "$SCHEDULER_LOCATION" "$URL/process" "$INVOKER_SA" "$URL" "$SCHEDULE" \
       "Tidy Gmail: newsletters / notifications / promotions (POST /process)"; then
  warn "Scheduler job NOT created. Retry with SCHEDULER_LOCATION=<region from: gcloud scheduler locations list> $0 --skip-build"
fi

say "Done"
echo "  Run now:   gcloud scheduler jobs run mailagent-tidy --location $SCHEDULER_LOCATION"
echo "  Read log:  gcloud logging read 'resource.labels.service_name=\"$SERVICE\"' --limit 50 --format='value(jsonPayload)'"
[ "$LIVE" = 1 ] || echo "  Dry run is ON: nothing in the mailbox changes until you re-run with --live."
