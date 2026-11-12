"""learning_loop.check_pattern_hooks: only promote a skill to a hook that can actually run.

The loop used to write a hook record for ANY skill reaching its usage threshold, pointing at
scripts/preload_<skill>.py whether that file existed or not, with the interpreter's absolute path
(sys.executable) in the command and the promotion threshold copied into `risk_score`. Skills such as
`breakdown` or `agentic-router` (Claude Code skills, no preload script) got records that could never
work. These tests pin the fix.
"""

import json
import re
from pathlib import Path

import pytest

from scripts import learning_loop as ll

ROOT = Path(__file__).resolve().parent.parent


def _settings(counters=None, hooks=None):
    return {"hooks": list(hooks or []), "pattern_counters": dict(counters or {})}


def _audit(*skills):
    return {"skills_used": list(skills)}


@pytest.fixture
def scripts_dir(tmp_path):
    return tmp_path


def _make_script(scripts_dir, skill):
    (scripts_dir / f"preload_{skill}.py").write_text("print('ok')\n", encoding="utf-8")


# ── only a skill with a script is promoted ───────────────────────────────────


def test_a_skill_without_a_preload_script_is_not_promoted(scripts_dir):
    s = _settings({"breakdown": 2})
    changes = ll.check_pattern_hooks(s, _audit("breakdown"), scripts_dir=scripts_dir)
    assert changes == 0 and s["hooks"] == []
    assert s["pattern_counters"]["breakdown"] == 3  # the usage is still counted


def test_a_skill_with_a_script_is_promoted_at_the_threshold(scripts_dir):
    _make_script(scripts_dir, "foo_skill")
    s = _settings({"foo_skill": 2})
    assert ll.check_pattern_hooks(s, _audit("foo_skill"), scripts_dir=scripts_dir) == 1
    assert [h["id"] for h in s["hooks"]] == ["auto_preload_foo_skill"]


def test_below_the_threshold_nothing_happens_even_with_a_script(scripts_dir):
    _make_script(scripts_dir, "foo_skill")
    s = _settings({"foo_skill": 0})
    assert ll.check_pattern_hooks(s, _audit("foo_skill"), scripts_dir=scripts_dir) == 0
    assert s["hooks"] == []


def test_a_script_written_after_the_threshold_still_gets_its_hook_once(scripts_dir):
    """The old `==` test lost the chance forever if the file did not exist at the exact moment."""
    s = _settings({"foo_skill": 7})
    assert ll.check_pattern_hooks(s, _audit("foo_skill"), scripts_dir=scripts_dir) == 0
    _make_script(scripts_dir, "foo_skill")
    assert ll.check_pattern_hooks(s, _audit("foo_skill"), scripts_dir=scripts_dir) == 1
    assert ll.check_pattern_hooks(s, _audit("foo_skill"), scripts_dir=scripts_dir) == 0  # no duplicate
    assert len(s["hooks"]) == 1


def test_an_existing_hook_is_never_duplicated(scripts_dir):
    _make_script(scripts_dir, "foo_skill")
    s = _settings({"foo_skill": 2}, hooks=[{"id": "auto_preload_foo_skill"}])
    assert ll.check_pattern_hooks(s, _audit("foo_skill"), scripts_dir=scripts_dir) == 0
    assert len(s["hooks"]) == 1


def test_the_tiered_threshold_still_applies(scripts_dir):
    skill = "gmail_api_integration"  # a security-tier name: promoted at 1, not 3
    assert ll.get_threshold_for_skill(skill) == 1
    _make_script(scripts_dir, skill)
    s = _settings()
    assert ll.check_pattern_hooks(s, _audit(skill), scripts_dir=scripts_dir) == 1


# ── what the record looks like ───────────────────────────────────────────────


def test_the_command_is_portable(scripts_dir):
    _make_script(scripts_dir, "foo_skill")
    s = _settings({"foo_skill": 2})
    ll.check_pattern_hooks(s, _audit("foo_skill"), scripts_dir=scripts_dir)
    command = s["hooks"][0]["command"]
    assert command == 'cd "$CLAUDE_PROJECT_DIR" && python scripts/preload_foo_skill.py 2>&1'
    assert not re.search(r"[A-Za-z]:[\\/]", command)  # no drive letter
    assert "python.exe" not in command


def test_the_threshold_is_not_passed_off_as_a_risk_score(scripts_dir):
    _make_script(scripts_dir, "foo_skill")
    s = _settings({"foo_skill": 2})
    ll.check_pattern_hooks(s, _audit("foo_skill"), scripts_dir=scripts_dir)
    hook = s["hooks"][0]
    assert "risk_score" not in hook
    assert hook["promotion_threshold"] == ll.get_threshold_for_skill("foo_skill")
    assert hook["promoted_from_pattern"] is True and hook["event"] == "PreToolUse"


# ── the skipped case is explained once, not every session ────────────────────


def test_the_skip_is_announced_once_at_the_threshold(scripts_dir, capsys):
    s = _settings({"breakdown": 2})
    ll.check_pattern_hooks(s, _audit("breakdown"), scripts_dir=scripts_dir)
    first = capsys.readouterr().out
    assert "breakdown" in first and "preload_breakdown.py" in first
    ll.check_pattern_hooks(s, _audit("breakdown"), scripts_dir=scripts_dir)  # counter is now 4
    assert capsys.readouterr().out == ""


# ── the real repository ──────────────────────────────────────────────────────


@pytest.mark.parametrize("skill", ["breakdown", "deep-agents-core", "agentic-router", "langgraph-persistence"])
def test_claude_code_skills_do_not_become_hooks_in_this_repo(skill):
    """No scripts/preload_<skill>.py exists for them, so the default scripts folder must refuse."""
    assert not (ROOT / "scripts" / f"preload_{skill}.py").exists()
    s = _settings({skill: ll.get_threshold_for_skill(skill) - 1})
    assert ll.check_pattern_hooks(s, _audit(skill)) == 0 and s["hooks"] == []


def test_every_recorded_preload_hook_points_at_a_real_script():
    data = json.loads((ROOT / "config" / "global_settings.json").read_text(encoding="utf-8"))
    for hook in data["hooks"]:
        if hook["id"].startswith("auto_preload_"):
            skill = hook["id"].removeprefix("auto_preload_")
            assert (ROOT / "scripts" / f"preload_{skill}.py").exists(), hook["id"]
            assert not re.search(r"[A-Za-z]:[\\/]", hook["command"]), hook["id"]


def test_the_docstring_does_not_claim_to_wire_hooks_into_claude_settings():
    doc = " ".join(ll.__doc__.split())  # one line, so wrapping does not matter
    assert "updates global_settings.json and .claude/settings.json" not in doc  # the old, false claim
    assert "not wired into .claude/settings.json" in doc.lower()
