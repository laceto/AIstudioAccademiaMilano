"""Tests for the Cloud Scheduler helpers in scripts/cloudrun_lib.sh (the stuck-job sweep).

Same approach as tests/test_deploy_cloudrun_lib.py: bash with a fake `gcloud`, nothing touches GCP.
The scheduler calls the private pipeline-worker's POST /sweep with an OIDC token minted for the
pipeline-tasks service account (audience = the worker URL), the same identity Cloud Tasks uses.
"""

import os
import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
LIB = (ROOT / "scripts" / "cloudrun_lib.sh").as_posix()
DEPLOY = (ROOT / "scripts" / "deploy_cloudrun.sh").read_text(encoding="utf-8")


def _bash() -> str | None:
    for candidate in (r"C:\Program Files\Git\bin\bash.exe", shutil.which("bash")):
        if candidate and Path(candidate).exists():
            return candidate
    return None


BASH = _bash()
needs_bash = pytest.mark.skipif(BASH is None, reason="bash not available")

FAKE = r"""
STORE="$1"; LOG="$STORE/calls.log"; shift
gcloud() {
  echo "gcloud $*" >> "$LOG"
  case "$1 $2" in
    "scheduler jobs")
      case "$3" in
        describe)       [ -f "$STORE/sched_$4" ] ;;
        create|update)  : > "$STORE/sched_$5" ;;  # gcloud scheduler jobs create http NAME
      esac ;;
  esac
}
env_val() { eval "printf '%s' \"\${FAKE_ENV_$1:-}\""; }
source "$LIB"
"""

ARGS = 'sweep-stuck-jobs europe-west6 "https://w.run.app/sweep" pipeline-tasks@p.iam.gserviceaccount.com "https://w.run.app" "*/10 * * * *"'


def _run(tmp_path, body):
    script = f'LIB="{LIB}"\n{FAKE}\n{body}'
    res = subprocess.run([BASH, "-c", script, "bash", tmp_path.as_posix()], capture_output=True, text=True, env={**os.environ})
    log = tmp_path / "calls.log"
    return res, (log.read_text() if log.exists() else "")


@needs_bash
def test_a_new_job_is_created_with_oidc_for_the_tasks_account(tmp_path):
    res, log = _run(tmp_path, f"ensure_scheduler_job {ARGS}")
    assert res.returncode == 0, res.stderr
    assert "created" in res.stdout
    assert "scheduler jobs create http sweep-stuck-jobs" in log and "jobs update" not in log
    for flag in (
        "--location=europe-west6", "--uri=https://w.run.app/sweep", "--http-method=POST",
        "--oidc-service-account-email=pipeline-tasks@p.iam.gserviceaccount.com",
        "--oidc-token-audience=https://w.run.app", "--schedule=*/10 * * * *",
    ):
        assert flag in log, flag


@needs_bash
def test_an_existing_job_is_reset_to_the_same_settings(tmp_path):
    (tmp_path / "sched_sweep-stuck-jobs").write_text("")
    res, log = _run(tmp_path, f"ensure_scheduler_job {ARGS}")
    assert res.returncode == 0, res.stderr
    assert "updated" in res.stdout
    assert "scheduler jobs update http sweep-stuck-jobs" in log and "jobs create" not in log
    assert "--oidc-token-audience=https://w.run.app" in log  # someone editing it in the console is undone


@needs_bash
def test_running_it_twice_ends_in_updated(tmp_path):
    _run(tmp_path, f"ensure_scheduler_job {ARGS}")
    res, _ = _run(tmp_path, f"ensure_scheduler_job {ARGS}")
    assert "updated" in res.stdout


# ── wiring in deploy_cloudrun.sh (it cannot run here: check the script text) ──


def test_the_deploy_enables_the_scheduler_api():
    assert "cloudscheduler.googleapis.com" in DEPLOY


def test_the_scheduler_gets_its_own_location_variable():
    assert 'SCHEDULER_LOCATION="${SCHEDULER_LOCATION:-' in DEPLOY


def test_the_scheduler_step_comes_after_the_worker_deploy_and_is_dry_run_aware():
    deploy = DEPLOY.index("Deploying pipeline-worker")
    url = DEPLOY.index("WORKER_URL=", deploy)
    step = DEPLOY.index("ensure_scheduler_job", url)
    assert deploy < url < step
    block = DEPLOY[step - 400: step + 400]
    assert "$DRY_RUN" in block
    assert '"$WORKER_URL/sweep"' in DEPLOY and "$TASKS_SA" in block
