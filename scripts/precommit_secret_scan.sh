#!/usr/bin/env bash
# Pre-commit secret scanner. Block the commit if staged content looks like
# credentials. Portable bash — works in Git Bash on Windows and Linux.
#
# Install (one-time, per clone):
#   ln -sf ../../scripts/precommit_secret_scan.sh .git/hooks/pre-commit
#   chmod +x .git/hooks/pre-commit
#
# Bypass (use sparingly, only when you understand the false positive):
#   git commit --no-verify ...

set -euo pipefail

red()    { printf '\033[31m%s\033[0m\n' "$*"; }
yellow() { printf '\033[33m%s\033[0m\n' "$*"; }

# 1. Block staging of literal .env files (but allow .env.example, .env.sample, .env.template)
env_files=$(git diff --cached --name-only --diff-filter=AM | grep -E '(^|/)\.env$' || true)
if [[ -n "$env_files" ]]; then
  red "BLOCKED: staged .env file(s):"
  echo "$env_files"
  echo "Use .env.example for templates. Remove with: git restore --staged <file>"
  exit 1
fi

# 2. Scan staged diff content for known secret patterns.
diff_content=$(git diff --cached -U0 --no-color | grep -E '^\+' | grep -vE '^\+\+\+ ' || true)
if [[ -z "$diff_content" ]]; then
  exit 0
fi

# Patterns: name|regex. Use ERE. Word boundaries where helpful.
patterns=(
  "OpenAI API key|sk-[A-Za-z0-9_-]{20,}"
  "Anthropic API key|sk-ant-[A-Za-z0-9_-]{20,}"
  "AWS access key|AKIA[0-9A-Z]{16}"
  "GitHub PAT (classic)|ghp_[A-Za-z0-9]{36}"
  "GitHub PAT (fine-grained)|github_pat_[A-Za-z0-9_]{60,}"
  "Slack bot token|xox[baprs]-[A-Za-z0-9-]{10,}"
  "Google API key|AIza[0-9A-Za-z_-]{35}"
  "Stripe secret key|sk_live_[A-Za-z0-9]{24,}"
  "Twilio auth token|SK[0-9a-fA-F]{32}"
  "Generic private key block|-----BEGIN ([A-Z]+ )?PRIVATE KEY-----"
  "Alpaca key assignment|ALPACA_(API_KEY|SECRET_KEY)[[:space:]]*=[[:space:]]*['\"][A-Z0-9]{16,}"
)

hits=0
while IFS='|' read -r label regex; do
  matches=$(echo "$diff_content" | grep -nE -e "$regex" || true)
  if [[ -n "$matches" ]]; then
    if [[ $hits -eq 0 ]]; then
      red "BLOCKED: possible secrets in staged diff."
    fi
    yellow "  [$label]"
    echo "$matches" | sed 's/^/    /'
    hits=1
  fi
done < <(printf '%s\n' "${patterns[@]}")

if [[ $hits -eq 1 ]]; then
  echo
  echo "If this is a false positive, bypass with: git commit --no-verify"
  echo "Otherwise: remove the secret, rotate it, and re-stage."
  exit 1
fi

exit 0
