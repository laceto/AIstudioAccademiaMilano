"""
ISS-005 (idempotency sub-issue): learning_loop.py must not reprocess
the same audit log on every Stop event.

The loop was firing on every Claude Code Stop event, re-running every
silent mutation (update_agent_stats avg, check_pattern_hooks counters),
and committing the resulting diff. Over an hour of normal use it produced
14 duplicate "learn: update global settings from request 014" commits.

These tests pin the fix:
  - skip when settings._meta.last_processed_audit_log matches the latest log
  - reprocess if --force is passed
  - commit_changes is a no-op when nothing is actually staged
"""

import json
import subprocess
import sys
from pathlib import Path
from unittest.mock import patch

import pytest

# Make `scripts` importable when running pytest from repo root
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from scripts import learning_loop  # noqa: E402


# ── Helpers ──────────────────────────────────────────────────────────────────

MINIMAL_AUDIT_YAML = """\
request_id: "999"
date: "2026-05-24"
intent: test_intent
outcome: success
agents_invoked:
  - name: TestAgent
    role: test
    duration_sec: 1
    status: success
skills_used: []
learning_flags:
  new_skills: []
  new_mcp: []
  risk_score: 1
"""

MINIMAL_AUDIT_MD = f"""# Audit Log — Test

```yaml
{MINIMAL_AUDIT_YAML}```
"""

MINIMAL_SETTINGS = {
    "_meta": {
        "version": "1.0",
        "last_updated": "2026-05-23",
        "last_request_id": "998",
        "total_requests_processed": 0,
    },
    "skills": {},
    "mcp": {},
    "agents": {},
    "hooks": [],
    "pattern_counters": {},
}


@pytest.fixture
def fake_repo(tmp_path: Path):
    """Spin up a minimal repo layout the loop can run against."""
    audit_dir = tmp_path / "audit"
    audit_dir.mkdir()
    audit_path = audit_dir / "2026-05-24_999_test.md"
    audit_path.write_text(MINIMAL_AUDIT_MD, encoding="utf-8")

    settings_path = tmp_path / "global_settings.json"
    settings_path.write_text(json.dumps(MINIMAL_SETTINGS, indent=2))

    req_registry = tmp_path / "requirements_registry.yaml"
    req_registry.write_text("products: {}\npricing: {}\n")

    intent_registry = tmp_path / "intent_registry.yaml"
    intent_registry.write_text("{}\n")

    return {
        "audit_dir": str(audit_dir),
        "audit_path": audit_path,
        "settings_path": str(settings_path),
        "req_registry": str(req_registry),
        "intent_registry": str(intent_registry),
    }


def _run_main(repo, argv_extra=()):
    argv = [
        "learning_loop.py",
        "--event", "delivery_complete",
        "--audit-dir", repo["audit_dir"],
        "--settings", repo["settings_path"],
        "--requirements-registry", repo["req_registry"],
        "--intent-registry", repo["intent_registry"],
        *argv_extra,
    ]
    # Always mock subprocess.run so the loop can't touch real git
    with patch("sys.argv", argv), patch.object(learning_loop.subprocess, "run") as mocked_run:
        # default: pretend git commands succeeded and there are NO staged changes
        mocked_run.return_value = subprocess.CompletedProcess(args=[], returncode=0)
        learning_loop.main()
    return mocked_run


# ── Tests ────────────────────────────────────────────────────────────────────

def test_first_run_processes_and_marks_audit_log(fake_repo):
    """Fresh settings → process → marker written."""
    _run_main(fake_repo)
    settings = json.loads(Path(fake_repo["settings_path"]).read_text())
    assert settings["_meta"].get("last_processed_audit_log") == "999"


def test_second_run_with_same_audit_log_is_a_noop(fake_repo):
    """Marker matches latest log → loop exits early, no mutation."""
    # Seed the marker so we look "already processed"
    settings = json.loads(Path(fake_repo["settings_path"]).read_text())
    settings["_meta"]["last_processed_audit_log"] = "999"
    Path(fake_repo["settings_path"]).write_text(json.dumps(settings, indent=2))
    before_mtime = Path(fake_repo["settings_path"]).stat().st_mtime_ns

    mocked_run = _run_main(fake_repo)

    # The settings file must not have been rewritten
    after_mtime = Path(fake_repo["settings_path"]).stat().st_mtime_ns
    assert before_mtime == after_mtime, "Settings file was rewritten on a no-op run"

    # No git command should have been issued
    git_calls = [c for c in mocked_run.call_args_list if c.args and c.args[0] and c.args[0][0] == "git"]
    assert not git_calls, f"Loop fired git commands on a no-op: {git_calls}"


def test_force_flag_reprocesses_even_if_marker_matches(fake_repo):
    """--force overrides the idempotency guard."""
    settings = json.loads(Path(fake_repo["settings_path"]).read_text())
    settings["_meta"]["last_processed_audit_log"] = "999"
    settings["_meta"]["total_requests_processed"] = 5
    Path(fake_repo["settings_path"]).write_text(json.dumps(settings, indent=2), encoding="utf-8")

    _run_main(fake_repo, argv_extra=["--force"])

    after = json.loads(Path(fake_repo["settings_path"]).read_text())
    assert after["_meta"]["total_requests_processed"] == 6, (
        "Forced run should have bumped the counter"
    )


def test_commit_changes_skips_when_nothing_staged(tmp_path, monkeypatch):
    """commit_changes() must not run `git commit` if `git diff --cached --quiet` says clean."""
    monkeypatch.chdir(tmp_path)
    settings_file = tmp_path / "settings.json"
    settings_file.write_text("{}")
    audit_dir = tmp_path / "audit"
    audit_dir.mkdir()

    git_calls = []

    def fake_run(cmd, *args, **kwargs):
        git_calls.append(list(cmd))
        # `git diff --cached --quiet` exits 0 when there is NO diff
        if cmd[:3] == ["git", "diff", "--cached"]:
            return subprocess.CompletedProcess(args=cmd, returncode=0)
        return subprocess.CompletedProcess(args=cmd, returncode=0)

    monkeypatch.setattr(learning_loop.subprocess, "run", fake_run)

    learning_loop.commit_changes(str(settings_file), str(audit_dir), "999")

    commands_run = [c[1] for c in git_calls if len(c) > 1]
    assert "commit" not in commands_run, (
        f"commit_changes ran `git commit` despite empty staged diff: {git_calls}"
    )
    assert "push" not in commands_run, (
        f"commit_changes ran `git push` despite empty staged diff: {git_calls}"
    )


def test_commit_changes_does_commit_when_diff_present(tmp_path, monkeypatch):
    """Symmetric: when there IS a staged diff, commit + push proceed normally."""
    monkeypatch.chdir(tmp_path)
    settings_file = tmp_path / "settings.json"
    settings_file.write_text("{}")
    audit_dir = tmp_path / "audit"
    audit_dir.mkdir()

    git_calls = []

    def fake_run(cmd, *args, **kwargs):
        git_calls.append(list(cmd))
        # Pretend there IS a diff: exit 1 from `git diff --cached --quiet`
        if cmd[:3] == ["git", "diff", "--cached"]:
            return subprocess.CompletedProcess(args=cmd, returncode=1)
        return subprocess.CompletedProcess(args=cmd, returncode=0)

    monkeypatch.setattr(learning_loop.subprocess, "run", fake_run)

    learning_loop.commit_changes(str(settings_file), str(audit_dir), "999")

    commands_run = [c[1] for c in git_calls if len(c) > 1]
    assert "commit" in commands_run, (
        f"commit_changes failed to run `git commit` despite staged diff: {git_calls}"
    )
