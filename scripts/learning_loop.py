"""
Learning Loop — AI Studio Accademia Milano

Runs after every completed request. Reads the latest audit log,
extract new skills / MCP / hook patterns, updates global_settings.json
and .claude/settings.json, then commits if risk_score < 3.
"""

import argparse
import json
import re
import subprocess
from datetime import datetime
from pathlib import Path

import yaml  # pip install pyyaml


# ── Tiered thresholds ────────────────────────────────────────────────────────

_SECURITY_PATTERNS = ("_oauth", "_api_key", "_api_integration")
_WRITE_PATTERNS = ("_deploy", "_send", "_push", "_write")


def get_threshold_for_skill(skill_name: str) -> int:
    """Return the pattern-promotion threshold for a skill based on its risk tier."""
    for pat in _SECURITY_PATTERNS:
        if pat in skill_name:
            return 1
    for pat in _WRITE_PATTERNS:
        if pat in skill_name:
            return 2
    return 3


# ── Advisory output validation ───────────────────────────────────────────────

_DISCLAIMER_RE = re.compile(
    r"(does not constitute regulated|AI knowledge and general business principles"
    r"|not constitute.*?advice)",
    re.IGNORECASE | re.DOTALL,
)


def _has_disclaimer(text: str) -> bool:
    return bool(_DISCLAIMER_RE.search(text))


def validate_advisory_output(text: str, min_words: int = 0) -> bool:
    """Validate that an advisory report has a disclaimer in the right position."""
    if not text or not text.strip():
        raise ValueError("Report is empty")

    if not _has_disclaimer(text):
        raise ValueError("Report missing disclaimer")

    # Check placement: disclaimer must be in first or last 20% of lines
    lines = text.splitlines()
    disclaimer_idx = next(
        (i for i, ln in enumerate(lines) if _has_disclaimer(ln)), None
    )
    if disclaimer_idx is not None:
        position = disclaimer_idx / max(len(lines) - 1, 1)
        if 0.20 < position < 0.80:
            raise ValueError(
                "Disclaimer placement: must appear at the top or bottom of the report"
            )

    # Content check: report must have substance beyond the disclaimer
    content_lines = [ln for ln in lines if not _has_disclaimer(ln)]
    content = " ".join(content_lines).strip()
    if not content:
        raise ValueError("Report has no content beyond the disclaimer")

    word_count = len(content.split())
    if word_count < min_words:
        raise ValueError(
            f"Report too short: {word_count} words, minimum {min_words}"
        )

    return True


# ── Settings helpers ─────────────────────────────────────────────────────────

def load_settings(settings_path: str) -> dict:
    with open(settings_path) as f:
        return json.load(f)


def save_settings(settings: dict, settings_path: str) -> None:
    with open(settings_path, "w") as f:
        json.dump(settings, f, indent=2)
    print(f"[learning_loop] Settings saved to {settings_path}")


def latest_audit_log(audit_dir: str) -> Path:
    # Only match date-prefixed audit logs (YYYY-MM-DD_NNN_*.md), skip README etc.
    logs = sorted(Path(audit_dir).glob("[0-9][0-9][0-9][0-9]-*.md"))
    return logs[-1] if logs else None


def parse_audit_log(log_path: Path) -> dict:
    text = log_path.read_text()
    match = re.search(r"```yaml\n(.+?)```", text, re.DOTALL)
    if not match:
        raise ValueError(f"No YAML block found in {log_path}")
    return yaml.safe_load(match.group(1))


# ── Learning functions ───────────────────────────────────────────────────────

def update_skills(settings: dict, audit: dict) -> int:
    changes = 0
    today = datetime.now().strftime("%Y-%m-%d")
    for skill in audit.get("learning_flags", {}).get("new_skills", []) or []:
        if skill not in settings["skills"]:
            settings["skills"][skill] = {
                "description": f"Auto-discovered from request {audit['request_id']}",
                "intent_mappings": [audit["intent"]],
                "agent": "unknown",
                "first_seen": today,
                "times_used": 1,
                "success_rate": 1.0 if audit["outcome"] == "success" else 0.0,
                "avg_duration_sec": 0,
            }
            print(f"[learning_loop] New skill: {skill}")
            changes += 1
        else:
            settings["skills"][skill]["times_used"] = (
                settings["skills"][skill].get("times_used", 0) + 1
            )
    return changes


def update_mcp(settings: dict, audit: dict) -> int:
    changes = 0
    today = datetime.now().strftime("%Y-%m-%d")
    for tool in audit.get("learning_flags", {}).get("new_mcp", []) or []:
        if tool not in settings["mcp"]:
            settings["mcp"][tool] = {
                "description": f"Auto-discovered from request {audit['request_id']}",
                "endpoint": "unknown",
                "auth": "unknown",
                "write_access": False,
                "avg_latency_sec": 0,
                "first_seen": today,
                "times_used": 1,
                "failure_rate": 0.0,
            }
            print(f"[learning_loop] New MCP tool: {tool}")
            changes += 1
    return changes


def update_agent_stats(settings: dict, audit: dict) -> int:
    changes = 0
    intent = audit.get("intent", "unknown")
    for agent_entry in audit.get("agents_invoked", []):
        name = agent_entry["name"]
        if name not in settings.setdefault("agents", {}):
            settings["agents"][name] = {"roles": [], "capabilities": [], "task_stats": {}}
        stats = settings["agents"][name].setdefault("task_stats", {})
        if intent not in stats:
            stats[intent] = {"count": 0, "avg_sec": 0, "success_rate": 1.0}
            changes += 1
        s = stats[intent]
        n = s["count"]
        s["avg_sec"] = round(
            (s["avg_sec"] * n + agent_entry.get("duration_sec", 0)) / (n + 1), 1
        )
        s["count"] = n + 1
        if agent_entry["status"] != "success":
            s["success_rate"] = round((s["success_rate"] * n) / (n + 1), 3)
    return changes


def check_pattern_hooks(settings: dict, audit: dict) -> int:
    """Promote recurring skill patterns to hooks using tiered thresholds."""
    changes = 0
    counters = settings.setdefault("pattern_counters", {})

    for skill in audit.get("skills_used", []):
        counters[skill] = counters.get(skill, 0) + 1
        threshold = get_threshold_for_skill(skill)
        if counters[skill] == threshold:
            hook_id = f"auto_preload_{skill}"
            existing_ids = [h["id"] for h in settings.get("hooks", [])]
            if hook_id not in existing_ids:
                new_hook = {
                    "id": hook_id,
                    "event": "PreToolUse",
                    "matcher": skill,
                    "description": (
                        f"Auto-promoted: pre-load {skill} context after {threshold} uses"
                    ),
                    "command": f"python3 scripts/preload_{skill}.py 2>&1",
                    "added": datetime.now().strftime("%Y-%m-%d"),
                    "promoted_from_pattern": True,
                    "times_fired": 0,
                    "risk_score": threshold,
                }
                settings.setdefault("hooks", []).append(new_hook)
                print(f"[learning_loop] New hook promoted: {hook_id}")
                changes += 1
    return changes


def update_requirements_registry(registry_path: str, audit: dict) -> int:
    """Add new product types from audit learning_flags to requirements_registry.yaml."""
    changes = 0
    new_types = audit.get("learning_flags", {}).get("new_product_types", {})
    if not new_types:
        return 0
    with open(registry_path) as f:
        registry = yaml.safe_load(f)
    new_pricing = audit.get("learning_flags", {}).get("new_pricing", {})
    for product_type, spec in new_types.items():
        if product_type not in registry.get("products", {}):
            registry.setdefault("products", {})[product_type] = spec
            if product_type in new_pricing:
                registry.setdefault("pricing", {})[product_type] = new_pricing[product_type]
            print(f"[learning_loop] New product type in requirements registry: {product_type}")
            changes += 1
    if changes:
        with open(registry_path, "w") as f:
            yaml.dump(registry, f, default_flow_style=False, allow_unicode=True, sort_keys=False)
    return changes


def update_intent_registry(intent_registry_path: str, audit: dict) -> int:
    """Add new intents from audit learning_flags to process/intent_registry.yaml."""
    changes = 0
    new_intents = audit.get("learning_flags", {}).get("new_intents", [])
    if not new_intents:
        return 0
    with open(intent_registry_path) as f:
        registry = yaml.safe_load(f) or {}
    for intent in new_intents:
        if intent not in registry:
            registry[intent] = {
                "skills": audit.get("skills_used", []),
                "delivery_options": ["github_repo"],
            }
            print(f"[learning_loop] New intent registered: {intent}")
            changes += 1
    if changes:
        with open(intent_registry_path, "w") as f:
            yaml.dump(registry, f, default_flow_style=False, allow_unicode=True, sort_keys=False)
    return changes


def commit_changes(settings_path: str, audit_dir: str, request_id: str) -> None:
    files = [
        settings_path,
        ".claude/settings.json",
        "config/requirements_registry.yaml",
        "process/intent_registry.yaml",
        "CLAUDE.md",
    ]
    for f in files:
        subprocess.run(["git", "add", f], check=False)
    subprocess.run(["git", "add", audit_dir], check=False)
    # Don't commit a no-op: if nothing is actually staged-different, bail.
    # `git diff --cached --quiet` exits 0 when there's no diff, 1 when there is.
    diff = subprocess.run(["git", "diff", "--cached", "--quiet"], check=False)
    if diff.returncode == 0:
        print("[learning_loop] No staged changes — skipping commit.")
        return
    msg = f"learn: update global settings from request {request_id}"
    subprocess.run(["git", "commit", "-m", msg], check=False)
    subprocess.run(["git", "push"], check=False)
    print(f"[learning_loop] Committed: {msg}")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--event", required=True, choices=["session_end", "delivery_complete"]
    )
    parser.add_argument("--audit-dir", default="process/audit")
    parser.add_argument("--settings", default="config/global_settings.json")
    parser.add_argument("--requirements-registry", default="config/requirements_registry.yaml")
    parser.add_argument("--intent-registry", default="process/intent_registry.yaml")
    parser.add_argument(
        "--force",
        action="store_true",
        help="Reprocess the latest audit log even if it was already marked processed.",
    )
    args = parser.parse_args()

    log_path = latest_audit_log(args.audit_dir)
    if not log_path:
        print("[learning_loop] No audit logs found. Nothing to learn.")
        return

    settings = load_settings(args.settings)

    # Idempotency: don't reprocess the same audit log on every Stop event.
    # Several mutators (update_agent_stats avg, check_pattern_hooks counters)
    # touch settings without bumping the `changes` counter, which made every
    # rerun look like new work and produced duplicate `learn:` commits.
    last_processed = settings.get("_meta", {}).get("last_processed_audit_log")
    if last_processed == log_path.name and not args.force:
        print(
            f"[learning_loop] {log_path.name} already processed "
            f"(set _meta.last_processed_audit_log). Pass --force to override."
        )
        return

    print(f"[learning_loop] Processing: {log_path.name}")
    audit = parse_audit_log(log_path)

    risk_score = audit.get("learning_flags", {}).get("risk_score", 1)
    changes = 0
    changes += update_skills(settings, audit)
    changes += update_mcp(settings, audit)
    changes += update_agent_stats(settings, audit)
    changes += check_pattern_hooks(settings, audit)
    changes += update_requirements_registry(args.requirements_registry, audit)
    changes += update_intent_registry(args.intent_registry, audit)

    settings["_meta"]["last_updated"] = datetime.now().strftime("%Y-%m-%d")
    settings["_meta"]["last_request_id"] = audit["request_id"]
    settings["_meta"]["last_processed_audit_log"] = log_path.name
    settings["_meta"]["total_requests_processed"] = (
        settings["_meta"].get("total_requests_processed", 0) + 1
    )

    save_settings(settings, args.settings)
    print(f"[learning_loop] {changes} changes. Risk score: {risk_score}")

    if risk_score < 3:
        commit_changes(args.settings, args.audit_dir, audit["request_id"])
    else:
        print(
            f"[learning_loop] Risk score {risk_score} >= 3. "
            "Awaiting Luigi approval before commit."
        )


if __name__ == "__main__":
    main()
