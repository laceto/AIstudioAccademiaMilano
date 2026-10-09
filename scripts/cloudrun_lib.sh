#!/usr/bin/env bash
#
# cloudrun_lib.sh — functions used by deploy_cloudrun.sh, kept apart so the tests
# (tests/test_deploy_cloudrun_lib.py) can run them against a fake gcloud.
#
# Needs from the caller: gcloud on PATH (or a function), and env_val NAME
# (prints a value from .env).

# upsert_secret NAME VALUE
#
# Create the Secret Manager secret, or add a version only when the value changed.
# Every extra active version beyond the free 6 costs money, and an unchanged value
# does not need one. The value goes through stdin: it never appears in a command line.
# Prints "NAME — created | unchanged | new version".
upsert_secret() {
  local name="$1" value="$2"
  if ! gcloud secrets describe "$name" >/dev/null 2>&1; then
    printf '%s' "$value" | gcloud secrets create "$name" --data-file=- --replication-policy=automatic >/dev/null
    echo "  $name — created"
  elif [ "$(gcloud secrets versions access latest --secret="$name" 2>/dev/null)" = "$value" ]; then
    echo "  $name — unchanged"
  else
    printf '%s' "$value" | gcloud secrets versions add "$name" --data-file=- >/dev/null
    echo "  $name — new version"
  fi
}

# gateway_env_vars
#
# Value for `gcloud run deploy gateway --set-env-vars`: non-secret settings only.
#
# * "^|^" makes '|' the separator between KEY=VALUE pairs, because NOTIFY_EMAILS holds
#   commas and e-mail addresses hold '@'.
# * GATEWAY_QUEUE_DIR is deliberately absent: the Dockerfile sets it to /tmp/queue, and
#   Git Bash on Windows rewrites an argument such as KEY=/tmp/queue into
#   KEY=C:/Users/.../Temp/queue before gcloud sees it.
gateway_env_vars() {
  local store k v extra out
  store="$(env_val JOB_STORE)"
  out="^|^GATEWAY_SYNC_REPLY=1|JOB_STORE=${store:-firestore}"
  for k in NOTIFY_EMAILS NOTIFY_TELEGRAM_CHAT_IDS SMTP_USER SMTP_HOST SMTP_PORT NOTIFY_FROM PIPELINE_STALE_SECONDS; do
    v="$(env_val "$k")"
    [ -n "$v" ] && out="$out|$k=$v"
  done
  for extra in "$@"; do  # KEY=VALUE pairs computed by the caller (e.g. the worker URL)
    out="$out|$extra"
  done
  echo "$out"
}

# worker_env_vars
#
# Value for `gcloud run deploy pipeline-worker --set-env-vars`: settings only. The keys it needs
# (OPENAI_API_KEY, TELEGRAM_BOT_TOKEN, ...) travel as Secret Manager references, never here.
worker_env_vars() {
  local provider k v out
  provider="$(env_val PIPELINE_PROVIDER)"
  out="^|^JOB_STORE=firestore|PIPELINE_PROVIDER=${provider:-openai}"
  for k in NOTIFY_TELEGRAM_CHAT_IDS PIPELINE_RUN_TIMEOUT PIPELINE_STALE_SECONDS; do
    v="$(env_val "$k")"
    [ -n "$v" ] && out="$out|$k=$v"
  done
  echo "$out"
}

# ensure_service_account NAME PROJECT DISPLAY_NAME
#
# Create the service account if it does not exist. Prints "NAME — created | exists".
ensure_service_account() {
  local name="$1" project="$2" display="$3"
  if gcloud iam service-accounts describe "$name@$project.iam.gserviceaccount.com" >/dev/null 2>&1; then
    echo "  $name — exists"
  else
    gcloud iam service-accounts create "$name" --display-name="$display" >/dev/null
    echo "  $name — created"
  fi
}

# ensure_tasks_queue NAME LOCATION
#
# Create the Cloud Tasks queue, or reset an existing one to the same settings. A pipeline run
# costs LLM money, so a failed task must never be retried on its own (max-attempts=1) and at most
# a couple may run at once; someone loosening that in the console is undone by the next deploy.
# Prints "NAME — created | updated".
ensure_tasks_queue() {
  local name="$1" location="$2"
  local flags=(--max-attempts=1 --max-concurrent-dispatches=2 --max-dispatches-per-second=1)
  if gcloud tasks queues describe "$name" --location="$location" >/dev/null 2>&1; then
    gcloud tasks queues update "$name" --location="$location" "${flags[@]}" >/dev/null
    echo "  $name — updated"
  else
    gcloud tasks queues create "$name" --location="$location" "${flags[@]}" >/dev/null
    echo "  $name — created"
  fi
}

# _random_secret
#
# 64 hex characters: within what Telegram accepts for a webhook secret_token (A-Z a-z 0-9 _ -, 1-256).
_random_secret() {
  if command -v openssl >/dev/null 2>&1; then
    openssl rand -hex 32
  else
    python3 -c 'import secrets; print(secrets.token_hex(32))'
  fi
}

# resolve_webhook_secret
#
# The value registered with Telegram's setWebhook as secret_token and checked by the gateway on
# every update (header X-Telegram-Bot-Api-Secret-Token). Order: TELEGRAM_WEBHOOK_SECRET from .env,
# else the one already in Secret Manager, else a fresh random one. It is stored in Secret Manager
# (new version only if it changed) and printed on stdout, and nothing else is.
resolve_webhook_secret() {
  local value
  value="$(env_val TELEGRAM_WEBHOOK_SECRET)"
  if [ -z "$value" ]; then
    value="$(gcloud secrets versions access latest --secret=TELEGRAM_WEBHOOK_SECRET 2>/dev/null || true)"
  fi
  [ -n "$value" ] || value="$(_random_secret)"
  upsert_secret TELEGRAM_WEBHOOK_SECRET "$value" >/dev/null
  printf '%s' "$value"
}

# ensure_scheduler_job NAME LOCATION URI SERVICE_ACCOUNT_EMAIL AUDIENCE SCHEDULE
#
# Create the Cloud Scheduler HTTP job, or reset an existing one to the same settings. It POSTs to URI
# with an OIDC token minted for SERVICE_ACCOUNT_EMAIL (audience = the private service's URL), so the
# call is authorised exactly like Cloud Tasks'. Used for the stuck-job sweep (pipeline-worker /sweep).
# Prints "NAME — created | updated".
ensure_scheduler_job() {
  local name="$1" location="$2" uri="$3" sa="$4" audience="$5" schedule="$6"
  local flags=(
    --location="$location" --schedule="$schedule" --uri="$uri" --http-method=POST
    --oidc-service-account-email="$sa" --oidc-token-audience="$audience"
    --time-zone=Etc/UTC --attempt-deadline=120s
    --description="Fail pipeline jobs stuck in running (POST /sweep)"
  )
  if gcloud scheduler jobs describe "$name" --location="$location" >/dev/null 2>&1; then
    gcloud scheduler jobs update http "$name" "${flags[@]}" >/dev/null
    echo "  $name — updated"
  else
    gcloud scheduler jobs create http "$name" "${flags[@]}" >/dev/null
    echo "  $name — created"
  fi
}
