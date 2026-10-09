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
