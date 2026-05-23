"""
Learning Loop — AI Studio Accademia Milano

Runs after every completed request. Reads the latest audit log,
extract new skills / MCP / hook patterns, updates global_settings.json
and .claude/settings.json, then commits if risk_score < 3.
"""

import argparse
import json
import os
import re
import subprocess
from datetime import datetime
from pathlib import Path

import yaml  # pip install pyyaml


def load_settings(settings_path: str) -> dict:
    with open(settings_path) as f:
        return json.load(f)


def save_settings(settings: dict, settings_path: str) -> None:
    with open(settings_path, "w") as f:
        json.dump(settings, f, indent=2)
    print(f"[learning_loop] Settings saved to {settings_path}")


def latest_audit_log(audit_dir: str) -> Path | None:
    logs = sorted(Path(audit_dir).glob("*.md"))
    return logs[-1] if logs else None


def parse_audit_log(log_path: Path) -> dict:
    """Extract the YAML front-matter block from the audit log."""
    text = log_path.read_text()
    match = re.search(r"```yaml\n(.+?)```", text, re.DOTALL)
    if not match:
        raise ValueError(f"No YAML block found in {log_path}")
    return yaml.safe_load(match.group(1))


def update_skills(settings: dict, audit: dict) -> int:
    """Add newly seen skills. Returns count of changes."""
    changes = 0
    today = datetime.now().strftime("%Y-%m-%d")
    for skill in audit.get("learning_flags", {}).get("new_skills", []):
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
            s = settings["skills"][skill]
            s["times_used"] = s.get("times_used", 0) + 1
    return changes


def update_mcp(settings: dict, audit: dict) -> int:
    """Register newly seen MCP tools. Returns count of changes."""
    changes = 0
    today = datetime.now().strftime("%Y-%m-%d")
    for tool in audit.get("learning_flags", {}).get("new_mcp", []):
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
    """Update per-agent task statistics. Returns count of changes."""
    changes = 0
    intent = audit.get("intent", "unknown")
    for agent_entry in audit.get("agents_invoked", []):
        name = agent_entry["name"]
        if name not in settings["agents"]:
            settings["agents"][name] = {"roles": [], "capabilities": [], "task_stats": {}}
        stats = settings["agents"][name].setdefault("task_stats", {})
        if intent not in stats:
            stats[intent] = {"count": 0, "avg_sec": 0, "success_rate": 1.0}
            changes += 1
        s = stats[intent]
        n = s["count"]
        s["avg_sec"] = round((s["avg_sec"] * n + agent_entry.get("duration_sec", 0)) / (n + 1), 1)
        s["count"] = n + 1
        if agent_entry["status"] != "success":
            s["success_rate"] = round((s["success_rate"] * n) / (n + 1), 3)
    return changes


def check_pattern_hooks(settings: dict, audit: dict) -> int:
    """Promote recurring patterns to hooks when threshold is reached. Returns count of changes."""
    changes = 0
    threshold = settings.get("pattern_threshold", 3)
    counters = settings.setdefault("pattern_counters", {})

    for skill in audit.get("skills_used", []):
        counters[skill] = counters.get(skill, 0) + 1
        if counters[skill] == threshold:
            hook_id = f"auto_preload_{skill}"
            existing_ids = [h["id"] for h in settings.get("hooks", [])]
            if hook_id not in existing_ids:
                new_hook = {
                    "id": hook_id,
                    "event": "PreToolUse",
                    "matcher": skill,
                    "description": f"Auto-promoted: pre-load {skill} context after {threshold} uses",
                    "command": f"python3 scripts/preload_{skill}.py 2>&1",
                    "added": datetime.now().strftime("%Y-%m-%d"),
                    "promoted_from_pattern": True,
                    "times_fired": 0,
                    "risk_score": 2,
                }
                settings.setdefault("hooks", []).append(new_hook)
                print(f"[learning_loop] New hook promoted: {hook_id}")
                changes += 1
    return changes


def commit_changes(settings_path: str, audit_dir: str, request_id: str) -> None:
    files = [settings_path, ".claude/settings.json"]
    for f in files:
        subprocess.run(["git", "add", f], check=False)
    subprocess.run(["git", "add", audit_dir], check=False)
    msg = f"learn: update global settings from request {request_id}"
    subprocess.run(["git", "commit", "-m", msg], check=False)
    subprocess.run(["git", "push"], check=False)
    print(f"[learning_loop] Committed: {msg}")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--event", required=True, choices=["session_end", "delivery_complete"])
    parser.add_argument("--audit-dir", default="process/audit")
    parser.add_argument("--settings", default="config/global_settings.json")
    args = parser.parse_args()

    log_path = latest_audit_log(args.audit_dir)
    if not log_path:
        print("[learning_loop] No audit logs found. Nothing to learn.")
        return

    print(f"[learning_loop] Processing: {log_path.name}")
    audit = parse_audit_log(log_path)
    settings = load_settings(args.settings)

    risk_score = audit.get("learning_flags", {}).get("risk_score", 1)
    changes = 0
    changes += update_skills(settings, audit)
    changes += update_mcp(settings, audit)
    changes += update_agent_stats(settings, audit)
    changes += check_pattern_hooks(settings, audit)

    settings["_meta"]["last_updated"] = datetime.now().strftime("%Y-%m-%d")
    settings["_meta"]["last_request_id"] = audit["request_id"]
    settings["_meta"]["total_requests_processed"] = (
        settings["_meta"].get("total_requests_processed", 0) + 1
    )

    save_settings(settings, args.settings)
    print(f"[learning_loop] {changes} changes detected. Risk score: {risk_score}")

    if risk_score < 3:
        commit_changes(args.settings, args.audit_dir, audit["request_id"])
    else:
        print(f"[learning_loop] Risk score {risk_score} >= 3. Awaiting Luigi approval before commit.")


if __name__ == "__main__":
    main()
