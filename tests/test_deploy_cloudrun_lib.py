"""Tests for scripts/cloudrun_lib.sh — the testable parts of deploy_cloudrun.sh.

Run under bash with a fake `gcloud` function, so nothing touches GCP.

Two bugs they pin down, both found on the first real deploy:
  * every run added a new Secret Manager version even when the value had not changed
    (free tier is 6 active versions, so repeated deploys slowly start to cost);
  * GATEWAY_QUEUE_DIR=/tmp/queue was rewritten by Git Bash on Windows into
    C:/Users/.../Temp/queue before reaching gcloud. The Dockerfile already sets it, so the
    deploy must not pass it at all.
"""

import shutil
import subprocess
import sys
from pathlib import Path

import pytest

LIB = (Path(__file__).resolve().parent.parent / "scripts" / "cloudrun_lib.sh").as_posix()


def _bash() -> str | None:
    # On Windows plain `bash` can be WSL; the repo's scripts target Git Bash.
    for candidate in (r"C:\Program Files\Git\bin\bash.exe", shutil.which("bash")):
        if candidate and Path(candidate).exists():
            return candidate
    return None


BASH = _bash()
pytestmark = pytest.mark.skipif(BASH is None, reason="bash not available")

# Fake gcloud: records calls (never the secret value) and keeps secrets as files in $STORE.
FAKE = r"""
STORE="$1"; LOG="$STORE/calls.log"; shift
gcloud() {
  echo "gcloud $*" >> "$LOG"
  case "$1 $2" in
    "secrets describe") [ -f "$STORE/$3.secret" ] ;;
    "secrets create")   cat > "$STORE/$3.secret" ;;
    "secrets versions")
      case "$3" in
        add)    cat > "$STORE/$4.secret" ;;
        access) name="${5#--secret=}"; cat "$STORE/$name.secret" ;;
      esac ;;
    "iam service-accounts")
      case "$3" in
        describe) n="${4%%@*}"; [ -f "$STORE/sa_$n" ] ;;
        create)   : > "$STORE/sa_$4" ;;
      esac ;;
    "tasks queues")
      case "$3" in
        describe)      [ -f "$STORE/queue_$4" ] ;;
        create|update) : > "$STORE/queue_$4" ;;
      esac ;;
    "firestore fields")
      case "$4" in
        list)   [ -f "$STORE/list_fails" ] && return 1
                [ -f "$STORE/ttl_on" ] && echo "projects/p/databases/(default)/collectionGroups/jobs/fields/expire_at" ;;
        update) : > "$STORE/ttl_on" ;;
      esac ;;
    "firestore databases")
      case "$3" in
        describe) [ -f "$STORE/describe_fails" ] && return 1
                  if [ -f "$STORE/delete_protection" ]; then echo DELETE_PROTECTION_ENABLED; else echo DELETE_PROTECTION_DISABLED; fi ;;
        update)   : > "$STORE/delete_protection" ;;
      esac ;;
  esac
}
env_val() { eval "printf '%s' \"\${FAKE_ENV_$1:-}\""; }
source "$LIB"
"""


def _run(tmp_path, body, env=None):
    script = f'LIB="{LIB}"\n{FAKE}\n{body}'
    store = tmp_path.as_posix()
    res = subprocess.run(
        [BASH, "-c", script, "bash", store],
        capture_output=True, text=True, env={**__import__("os").environ, **(env or {})},
    )
    log = (tmp_path / "calls.log")
    return res, (log.read_text() if log.exists() else "")


# ── upsert_secret ────────────────────────────────────────────────────────────


def test_new_secret_is_created(tmp_path):
    res, log = _run(tmp_path, 'upsert_secret OPENAI_API_KEY "sk-abc"')
    assert res.returncode == 0, res.stderr
    assert "created" in res.stdout
    assert "secrets create OPENAI_API_KEY" in log and "versions add" not in log
    assert (tmp_path / "OPENAI_API_KEY.secret").read_text() == "sk-abc"


def test_unchanged_value_adds_no_version(tmp_path):
    (tmp_path / "OPENAI_API_KEY.secret").write_text("sk-abc")
    res, log = _run(tmp_path, 'upsert_secret OPENAI_API_KEY "sk-abc"')
    assert res.returncode == 0, res.stderr
    assert "unchanged" in res.stdout
    assert "versions add" not in log and "secrets create" not in log


def test_changed_value_adds_a_version(tmp_path):
    (tmp_path / "OPENAI_API_KEY.secret").write_text("old")
    res, log = _run(tmp_path, 'upsert_secret OPENAI_API_KEY "new-value"')
    assert res.returncode == 0, res.stderr
    assert "new version" in res.stdout
    assert "versions add OPENAI_API_KEY" in log
    assert (tmp_path / "OPENAI_API_KEY.secret").read_text() == "new-value"


def test_secret_value_never_appears_in_output_or_arguments(tmp_path):
    res, log = _run(tmp_path, 'upsert_secret SMTP_PASSWORD "hunter2hunter2"')
    assert "hunter2" not in res.stdout + res.stderr + log


def test_values_with_equals_and_spaces_are_compared_exactly(tmp_path):
    (tmp_path / "S.secret").write_text("a=b c")
    res, log = _run(tmp_path, 'upsert_secret S "a=b c"')
    assert "unchanged" in res.stdout and "versions add" not in log


# ── gateway_env_vars ─────────────────────────────────────────────────────────


def _env(tmp_path, **extra):
    res, _ = _run(
        tmp_path,
        "gateway_env_vars",
        env={f"FAKE_ENV_{k}": v for k, v in extra.items()},
    )
    assert res.returncode == 0, res.stderr
    return res.stdout.strip()


def test_env_vars_do_not_pass_the_queue_dir(tmp_path):
    out = _env(tmp_path)
    assert "GATEWAY_QUEUE_DIR" not in out
    assert "/tmp" not in out  # nothing for Git Bash to rewrite into a Windows path


def test_env_vars_default_to_firestore_and_sync_reply(tmp_path):
    out = _env(tmp_path)
    assert out.startswith("^|^")
    assert "GATEWAY_SYNC_REPLY=1" in out and "JOB_STORE=firestore" in out


def test_env_vars_honour_job_store_override(tmp_path):
    assert "JOB_STORE=file" in _env(tmp_path, JOB_STORE="file")


def test_env_vars_keep_commas_and_at_signs_in_emails(tmp_path):
    out = _env(tmp_path, NOTIFY_EMAILS="a@x.it,b@y.it", SMTP_USER="me@gmail.com")
    assert "|NOTIFY_EMAILS=a@x.it,b@y.it" in out and "|SMTP_USER=me@gmail.com" in out


def test_env_vars_omit_unset_optional_values(tmp_path):
    out = _env(tmp_path)
    for name in ("NOTIFY_EMAILS", "NOTIFY_TELEGRAM_CHAT_IDS", "SMTP_USER", "SMTP_HOST"):
        assert name not in out


# ── resolve_webhook_secret ───────────────────────────────────────────────────
# Telegram echoes this value in a header on every webhook call; the gateway refuses updates
# without it, which is what stops anyone forging "Luigi pressed Approve".


def test_webhook_secret_from_env_is_stored_and_returned(tmp_path):
    res, log = _run(tmp_path, "resolve_webhook_secret", env={"FAKE_ENV_TELEGRAM_WEBHOOK_SECRET": "from-env-123"})
    assert res.returncode == 0, res.stderr
    assert res.stdout == "from-env-123"  # nothing but the value on stdout
    assert (tmp_path / "TELEGRAM_WEBHOOK_SECRET.secret").read_text() == "from-env-123"


def test_webhook_secret_is_reused_from_secret_manager(tmp_path):
    (tmp_path / "TELEGRAM_WEBHOOK_SECRET.secret").write_text("already-there")
    res, log = _run(tmp_path, "resolve_webhook_secret")
    assert res.stdout == "already-there"
    assert "versions add" not in log and "secrets create" not in log  # no new version


def test_webhook_secret_is_generated_when_nobody_has_one(tmp_path):
    res, log = _run(tmp_path, '_random_secret() { printf "%s" "generated-xyz"; }\nresolve_webhook_secret')
    assert res.stdout == "generated-xyz"
    assert "secrets create TELEGRAM_WEBHOOK_SECRET" in log
    assert (tmp_path / "TELEGRAM_WEBHOOK_SECRET.secret").read_text() == "generated-xyz"


def test_the_default_generator_makes_a_telegram_safe_token(tmp_path):
    res, _ = _run(tmp_path, "_random_secret")
    token = res.stdout.strip()
    # Telegram allows 1-256 characters from A-Z a-z 0-9 _ -
    assert res.returncode == 0 and 32 <= len(token) <= 256
    assert all(c.isalnum() or c in "_-" for c in token)


def test_webhook_secret_never_appears_in_command_arguments(tmp_path):
    res, log = _run(tmp_path, "resolve_webhook_secret", env={"FAKE_ENV_TELEGRAM_WEBHOOK_SECRET": "topsecretvalue"})
    assert "topsecretvalue" not in log


# ── pipeline worker infrastructure ───────────────────────────────────────────


def test_the_tasks_service_account_is_created_once(tmp_path):
    res, log = _run(tmp_path, 'ensure_service_account pipeline-tasks proj "Pipeline tasks"')
    assert res.returncode == 0 and "created" in res.stdout
    assert "service-accounts create pipeline-tasks" in log
    res, log = _run(tmp_path, 'ensure_service_account pipeline-tasks proj "Pipeline tasks"')
    assert "exists" in res.stdout and "service-accounts create" not in log.split("describe")[-1]


def test_a_new_queue_never_retries_a_paid_run(tmp_path):
    res, log = _run(tmp_path, "ensure_tasks_queue pipeline-runs europe-west8")
    assert "created" in res.stdout and "queues create pipeline-runs --location=europe-west8" in log
    for flag in ("--max-attempts=1", "--max-concurrent-dispatches=2", "--max-dispatches-per-second=1"):
        assert flag in log


def test_an_existing_queue_is_reset_to_the_safe_settings(tmp_path):
    (tmp_path / "queue_pipeline-runs").write_text("")
    res, log = _run(tmp_path, "ensure_tasks_queue pipeline-runs europe-west8")
    assert "updated" in res.stdout and "queues update pipeline-runs" in log and "queues create" not in log
    assert "--max-attempts=1" in log  # someone raising it in the console would make failures cost twice


def test_gateway_env_vars_accepts_extra_settings(tmp_path):
    res, _ = _run(tmp_path, 'gateway_env_vars PIPELINE_QUEUE=pipeline-runs "PIPELINE_WORKER_URL=https://w.run.app"')
    out = res.stdout.strip()
    assert out.startswith("^|^") and "|PIPELINE_QUEUE=pipeline-runs" in out and "|PIPELINE_WORKER_URL=https://w.run.app" in out


def test_worker_env_vars_defaults(tmp_path):
    res, _ = _run(tmp_path, "worker_env_vars")
    out = res.stdout.strip()
    assert out.startswith("^|^") and "JOB_STORE=firestore" in out and "PIPELINE_PROVIDER=openai" in out
    assert "NOTIFY_TELEGRAM_CHAT_IDS" not in out  # nothing set in this environment


def test_worker_env_vars_carry_settings_but_never_secrets(tmp_path):
    res, _ = _run(
        tmp_path, "worker_env_vars",
        env={
            "FAKE_ENV_NOTIFY_TELEGRAM_CHAT_IDS": "5670736210", "FAKE_ENV_PIPELINE_PROVIDER": "anthropic",
            "FAKE_ENV_OPENAI_API_KEY": "k-should-not-appear", "FAKE_ENV_TELEGRAM_BOT_TOKEN": "t-should-not-appear",
            "FAKE_ENV_SMTP_PASSWORD": "p-should-not-appear",
        },
    )
    out = res.stdout
    assert "PIPELINE_PROVIDER=anthropic" in out and "NOTIFY_TELEGRAM_CHAT_IDS=5670736210" in out
    assert "should-not-appear" not in out  # secrets travel as Secret Manager references only


# ── Firestore retention and delete protection ────────────────────────────────
# Jobs hold what customers typed: they expire (TTL on expire_at) and the database cannot be
# deleted by accident. Both functions look first and change nothing that is already set.


def test_ttl_policy_is_enabled_on_expire_at_of_the_jobs_group(tmp_path):
    res, log = _run(tmp_path, "ensure_firestore_ttl")
    assert res.returncode == 0, res.stderr
    assert "enabled" in res.stdout
    assert "fields ttls update expire_at" in log and "--collection-group=jobs" in log and "--enable-ttl" in log
    assert (tmp_path / "ttl_on").exists()


def test_ttl_policy_already_set_is_left_alone(tmp_path):
    (tmp_path / "ttl_on").write_text("")
    res, log = _run(tmp_path, "ensure_firestore_ttl")
    assert res.returncode == 0, res.stderr
    assert "already" in res.stdout
    assert "ttls update" not in log


def test_ttl_policy_second_run_changes_nothing(tmp_path):
    _run(tmp_path, "ensure_firestore_ttl")
    res, log = _run(tmp_path, "ensure_firestore_ttl")
    assert log.count("ttls update") == 1  # the log accumulates across runs


def test_ttl_policy_follows_collection_and_field_arguments(tmp_path):
    res, log = _run(tmp_path, "ensure_firestore_ttl my_jobs when")
    assert "ttls update when" in log and "--collection-group=my_jobs" in log


def test_delete_protection_is_turned_on(tmp_path):
    res, log = _run(tmp_path, "ensure_delete_protection")
    assert res.returncode == 0, res.stderr
    assert "enabled" in res.stdout
    assert "databases update" in log and "--delete-protection" in log and "--no-delete-protection" not in log
    assert (tmp_path / "delete_protection").exists()


def test_delete_protection_already_on_is_left_alone(tmp_path):
    (tmp_path / "delete_protection").write_text("")
    res, log = _run(tmp_path, "ensure_delete_protection")
    assert res.returncode == 0, res.stderr
    assert "already" in res.stdout and "databases update" not in log


def test_delete_protection_second_run_changes_nothing(tmp_path):
    _run(tmp_path, "ensure_delete_protection")
    res, log = _run(tmp_path, "ensure_delete_protection")
    assert log.count("databases update") == 1


def test_the_deploy_script_wires_both_steps_after_the_database_exists():
    deploy = (Path(LIB).parent / "deploy_cloudrun.sh").read_text(encoding="utf-8")
    assert "ensure_firestore_ttl" in deploy and "ensure_delete_protection" in deploy
    create = deploy.index("firestore databases create")
    assert deploy.index("ensure_firestore_ttl") > create and deploy.index("ensure_delete_protection") > create


# The deploy runs under `set -euo pipefail`: a failing look-up must warn and carry on, not abort silently.


def test_delete_protection_survives_a_failing_describe_under_strict_mode(tmp_path):
    (tmp_path / "describe_fails").write_text("")
    res, log = _run(tmp_path, "set -euo pipefail\nensure_delete_protection\necho after")
    assert res.returncode == 0, res.stderr
    assert "after" in res.stdout and "WARN" in res.stderr + res.stdout
    assert "databases update" in log and (tmp_path / "delete_protection").exists()


def test_ttl_check_is_not_fooled_by_sigpipe_under_pipefail(tmp_path):
    (tmp_path / "ttl_on").write_text("")
    # a gcloud that prints a lot, so that `grep -q` closing the pipe early would SIGPIPE it
    body = (
        "set -euo pipefail\n"
        'gcloud() { if [ "$3" = ttls ] && [ "$4" = list ]; then\n'
        '  echo "projects/p/databases/(default)/collectionGroups/jobs/fields/expire_at"\n'
        "  yes padding | head -n 200000 || true\n"
        'else echo "gcloud $*" >> "$STORE/calls.log"; fi; }\n'
        "ensure_firestore_ttl"
    )
    res, log = _run(tmp_path, body)
    assert res.returncode == 0, res.stderr
    assert "already" in res.stdout and "ttls update" not in log


def test_ttl_survives_a_failing_list_and_still_tries_to_enable(tmp_path):
    (tmp_path / "list_fails").write_text("")
    res, log = _run(tmp_path, "set -euo pipefail\nensure_firestore_ttl")
    assert res.returncode == 0, res.stderr
    assert "ttls update expire_at" in log

