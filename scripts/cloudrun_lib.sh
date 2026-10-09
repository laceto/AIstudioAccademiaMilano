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
  local store k v out
  store="$(env_val JOB_STORE)"
  out="^|^GATEWAY_SYNC_REPLY=1|JOB_STORE=${store:-firestore}"
  for k in NOTIFY_EMAILS NOTIFY_TELEGRAM_CHAT_IDS SMTP_USER SMTP_HOST SMTP_PORT NOTIFY_FROM; do
    v="$(env_val "$k")"
    [ -n "$v" ] && out="$out|$k=$v"
  done
  echo "$out"
}
