"""
Learning Loop — AI Studio Accademia Milano

Runs after every completed request. Reads the latest audit log,
extract new skills / MCP / hook patterns, updates global_settings.json
and .claude/settings.json, then commits if risk_score < 3.

Auto-promotion: skills that reach the skill_preload threshold (default 3)
are materialized as SKILL.md files in ~/.claude/skills/.
"""

import argparse
import os
import re
import subprocess
import sys
from datetime import datetime
from pathlib import Path
from textwrap import dedent

import yaml  # pip install pyyaml

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from config.brand import b, fmt
from scripts.settings_io import load_settings, save_settings, settings_lock


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


_AUDIT_LOG_RE = re.compile(r"^\d{4}-\d{2}-\d{2}_\d+_.+\.md$")


def latest_audit_log(audit_dir: str) -> Path:
    logs = sorted(
        p for p in Path(audit_dir).glob("*.md")
        if _AUDIT_LOG_RE.match(p.name)
    )
    return logs[-1] if logs else None


def parse_audit_log(log_path: Path) -> dict:
    try:
        text = log_path.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        text = log_path.read_text(encoding="utf-8", errors="replace")
    # fenced code block: ```yaml ... ```
    match = re.search(r"```yaml\n(.+?)```", text, re.DOTALL)
    if match:
        return yaml.safe_load(match.group(1))
    # YAML frontmatter: ---\n...\n---
    match = re.match(r"^---\n(.+?)\n---", text, re.DOTALL)
    if match:
        return yaml.safe_load(match.group(1))
    raise ValueError(f"No YAML block found in {log_path}")


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
        name = agent_entry.get("name", "unknown")
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

    for skill in audit.get("skills_used") or []:
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
                    "command": f'"{sys.executable}" scripts/preload_{skill}.py 2>&1',
                    "added": datetime.now().strftime("%Y-%m-%d"),
                    "promoted_from_pattern": True,
                    "times_fired": 0,
                    "risk_score": threshold,
                }
                settings.setdefault("hooks", []).append(new_hook)
                print(f"[learning_loop] New hook promoted: {hook_id}")
                changes += 1
    return changes


def _generate_skill_md(skill_name: str, skill_data: dict) -> str:
    """Generate a SKILL.md stub from global_settings.json skill metadata."""
    slug = skill_name.replace("_", "-")
    agent = skill_data.get("agent", "Chiara")
    intents = skill_data.get("intent_mappings", [])
    requires_auth = skill_data.get("requires_user_auth", False)
    auth_method = skill_data.get("auth_method", "")
    security_note = skill_data.get("security_note", "")
    times_used = skill_data.get("times_used", 0)
    intent_str = ", ".join(f"`{i}`" for i in intents) if intents else "general purpose"

    description = (
        f"{b('studio.name')} skill: {skill_name.replace('_', ' ')}. "
        f"Owner: {agent}. Intents: {', '.join(intents) or 'general'}. "
        f"Auto-promoted after {times_used} successful uses."
    )
    if requires_auth:
        description += f" Requires {auth_method} authentication."

    auth_block = ""
    if requires_auth:
        if auth_method == "api_key":
            auth_block = dedent("""\
                ## Authentication

                Read the API key from an environment variable — never hardcode.
                If the env var is missing, halt and tell Luigi exactly which one to set.
                """)
        elif auth_method in ("oauth2", "oauth1a", "oauth2_script", "device_code_oauth"):
            auth_block = dedent("""\
                ## Authentication

                Use OAuth via `scripts/credential_manager.py`.
                Token is session-scoped only — discard after use, never write to disk.
                """)
        elif auth_method == "webhook_url":
            auth_block = dedent("""\
                ## Authentication

                Read the webhook URL from an environment variable.
                Never log or commit the URL.
                """)

    security_block = f"\n## Security note\n\n{security_note}\n" if security_note else ""

    return dedent(f"""\
        ---
        name: {slug}
        description: '{description}'
        ---

        # {skill_name.replace("_", " ").title()}

        **Owner:** {agent}
        **Intent mappings:** {intent_str}
        **Times used:** {times_used} (auto-promoted by learning loop)

        ## When to use

        Invoke when the current task involves `{skill_name}` or any of: {intent_str}.

        {auth_block}{security_block}
        ## Studio pipeline

        This skill is part of the 6-agent pipeline:
        Stacy -> Gianni -> Chiara -> Stacy QA -> Marco -> Francesca.
        Coordinate with the owning agent ({agent}) for implementation details.

        ## Hand-craft this skill

        This stub was auto-generated. Replace it with a full SKILL.md when
        you have enough examples to document the exact steps, code patterns,
        and edge cases for `{skill_name}`.
        """)


def promote_skills_to_files(settings: dict, skills_dir: Path) -> int:
    """Auto-create SKILL.md stubs for skills that have reached the promotion threshold."""
    if not skills_dir.exists():
        print(f"[learning_loop] Skills dir not found: {skills_dir} — skipping promotion")
        return 0

    threshold = settings.get("pattern_thresholds", {}).get("skill_preload", 3)
    changes = 0

    for skill_name, skill_data in settings.get("skills", {}).items():
        if skill_data.get("times_used", 0) < threshold:
            continue

        slug = skill_name.replace("_", "-")
        skill_file = skills_dir / slug / "SKILL.md"

        if skill_file.exists():
            continue  # already promoted — hand-crafted or previous run

        skill_file.parent.mkdir(parents=True, exist_ok=True)
        skill_file.write_text(_generate_skill_md(skill_name, skill_data), encoding="utf-8")
        print(f"[learning_loop] Promoted skill -> ~/.claude/skills/{slug}/SKILL.md")
        changes += 1

    return changes


_TEMPLATE_CANDIDATE_THRESHOLD = 2


def check_template_candidates(settings: dict, templates_dir: str = "templates") -> int:
    """Flag skills whose times_used crosses the template candidate threshold.

    Writes new entries to settings['template_candidates']. Skips skills that
    are already flagged or already have a template file on disk.
    """
    candidates = settings.setdefault("template_candidates", {})
    today = datetime.now().strftime("%Y-%m-%d")
    changes = 0

    for skill_name, skill_data in settings.get("skills", {}).items():
        if skill_data.get("times_used", 0) < _TEMPLATE_CANDIDATE_THRESHOLD:
            continue
        if skill_name in candidates:
            continue

        # Skip if a template file already covers this skill
        slug = skill_name.replace("_", "-")
        existing = list(Path(templates_dir).rglob(f"{slug}.py")) if Path(templates_dir).exists() else []
        if existing:
            continue

        candidates[skill_name] = {
            "flagged_date": today,
            "times_used": skill_data.get("times_used", 0),
            "intent_mappings": skill_data.get("intent_mappings", []),
            "status": "pending",
        }
        print(f"[learning_loop] Template candidate: {skill_name} (used {skill_data.get('times_used')}x)")
        changes += 1

    return changes


def update_studio_wiki(audit: dict, settings: dict) -> int:
    """Append a new row to wiki/studio/01_deliverables.md after a successful delivery."""
    if not audit:
        return 0
    if audit.get("outcome") != "success":
        return 0

    request_id = audit.get("request_id", "")
    date = audit.get("date", datetime.now().strftime("%Y-%m-%d"))
    intent = audit.get("intent", "unknown")
    price_raw = audit.get("price", None)
    path = audit.get("deliverable_path", "")

    if not request_id or not price_raw:
        return 0

    price = f"€{price_raw}" if not str(price_raw).startswith("€") else str(price_raw)
    skills = audit.get("skills_used", [])
    stack = ", ".join(skills[:3]) if skills else intent

    wiki_path = Path(__file__).parent.parent / "wiki" / "studio" / "01_deliverables.md"
    if not wiki_path.exists():
        return 0

    content = wiki_path.read_text(encoding="utf-8")

    # Deduplicate — skip if request_id already in the table
    if f"| {request_id} |" in content:
        return 0

    new_row = f"| {request_id} | {date} | {intent} | {stack} | {price} | `{path}` |"

    # Insert before the Revenue Summary section
    marker = "\n## Revenue Summary"
    if marker in content:
        content = content.replace(marker, f"\n{new_row}{marker}")
    else:
        content = content.rstrip() + f"\n{new_row}\n"

    # Update "Last updated" header line
    content = re.sub(
        r"Last updated: \d{4}-\d{2}-\d{2}",
        f"Last updated: {datetime.now().strftime('%Y-%m-%d')}",
        content,
    )

    wiki_path.write_text(content, encoding="utf-8")
    print(f"[learning_loop] Studio wiki updated: request {request_id} appended.")
    return 1


def update_requirements_registry(registry_path: str, audit: dict) -> int:
    """Add new product types from audit learning_flags to requirements_registry.yaml."""
    changes = 0
    new_types = audit.get("learning_flags", {}).get("new_product_types", {})
    if not new_types:
        return 0
    with open(registry_path, encoding="utf-8") as f:
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
        with open(registry_path, "w", encoding="utf-8") as f:
            yaml.dump(registry, f, default_flow_style=False, allow_unicode=True, sort_keys=False)
    return changes


def update_intent_registry(intent_registry_path: str, audit: dict) -> int:
    """Add new intents from audit learning_flags to process/intent_registry.yaml."""
    changes = 0
    new_intents = audit.get("learning_flags", {}).get("new_intents", [])
    if not new_intents:
        return 0
    with open(intent_registry_path, encoding="utf-8") as f:
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
        with open(intent_registry_path, "w", encoding="utf-8") as f:
            yaml.dump(registry, f, default_flow_style=False, allow_unicode=True, sort_keys=False)
    return changes


def commit_changes(settings_path: str, audit_dir: str, request_id: str) -> None:
    result = subprocess.run(
        ["git", "rev-parse", "--abbrev-ref", "HEAD"],
        capture_output=True, text=True, check=False,
    )
    branch = (result.stdout or "").strip()
    if branch in ("main", "master", "HEAD"):
        print(f"[learning_loop] WARNING: on branch '{branch}' — skipping auto-commit to protect main/detached HEAD.")
        return

    files = [
        settings_path,
        ".claude/settings.json",
        "config/requirements_registry.yaml",
        "process/intent_registry.yaml",
    ]
    for f in files:
        subprocess.run(["git", "add", f], check=False)
    subprocess.run(["git", "add", audit_dir], check=False)
    diff = subprocess.run(["git", "diff", "--cached", "--quiet"], check=False)
    if diff.returncode == 0:
        print("[learning_loop] No staged changes — skipping commit.")
        return
    msg = f"learn: update global settings from request {request_id}"
    subprocess.run(["git", "commit", "-m", msg], check=False)
    push = subprocess.run(["git", "push"], capture_output=True, text=True, check=False)
    if push.returncode != 0:
        print(f"[learning_loop] WARNING: git push failed — commit is local only.\n{push.stderr.strip()}")
    else:
        print(f"[learning_loop] Committed and pushed: {msg}")


def save_to_claude_memory(settings: dict, audit, claude_dir: str) -> None:
    """Write live project state to Claude Code memory for future session context."""
    slug = (
        str(Path.cwd())
        .replace("\\", "-")
        .replace("/", "-")
        .replace(":", "-")
        .replace("_", "-")
    ).lstrip("-")
    memory_dir = Path(claude_dir) / "projects" / slug / "memory"
    memory_dir.mkdir(parents=True, exist_ok=True)

    meta = settings.get("_meta", {})
    open_issues = [i for i in settings.get("open_issues", []) if i.get("status") == "OPEN"]
    skills_count = len(settings.get("skills", {}))
    today = datetime.now().strftime("%Y-%m-%d")
    request_id = audit.get("request_id", "n/a") if audit else "n/a"
    intent = audit.get("intent", "n/a") if audit else "n/a"

    issue_lines = "\n".join(
        f"- [{i['id']}] {i['title']} ({i['priority']})" for i in open_issues
    ) or "_(none)_"

    content = dedent(f"""\
        ---
        name: project-state
        description: Live AI Studio state — updated by learning_loop.py after each session.
        metadata:
          type: project
        ---

        Last updated: {today}
        Last request: {request_id} (intent: {intent})
        Total requests processed: {meta.get('total_requests_processed', 0)}
        Skills registered: {skills_count}

        **Why:** Auto-saved by learning_loop.py so future sessions start with current state.
        **How to apply:** Quick orientation — avoids reading global_settings.json from scratch.

        ## Open Issues

        {issue_lines}
        """)

    state_file = memory_dir / "project_state.md"
    state_file.write_text(content, encoding="utf-8")
    print(f"[learning_loop] Memory -> {state_file}")

    memory_md = memory_dir / "MEMORY.md"
    if memory_md.exists():
        index = memory_md.read_text(encoding="utf-8")
        entry = "- [Project State](project_state.md) — Live studio state: requests processed, skills count, open issues"
        if "project_state.md" not in index:
            memory_md.write_text(index.rstrip() + f"\n{entry}\n", encoding="utf-8")
            print("[learning_loop] MEMORY.md updated")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--event", required=True, choices=["session_end", "delivery_complete"]
    )
    parser.add_argument("--audit-dir", default="process/audit")
    parser.add_argument("--settings", default="config/global_settings.json")
    parser.add_argument("--claude-dir", default=None,
                        help="Path to ~/.claude — writes project_state.md to memory/")
    parser.add_argument("--no-commit", action="store_true",
                        help="Skip git commit/push (used by CI)")
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

    print(f"[learning_loop] Processing: {log_path.name}")
    audit = parse_audit_log(log_path)

    with settings_lock(args.settings):
        settings = load_settings(args.settings)

        # Idempotency: guard by request_id (not filename) so slug renames don't re-trigger.
        # Migration shim: old format was a filename; strip to bare request_id on first run.
        last_processed_raw = settings.get("_meta", {}).get("last_processed_audit_log", "")
        last_processed = last_processed_raw.split("_")[2].split(".")[0] if "_" in str(last_processed_raw) else last_processed_raw
        if last_processed == audit.get("request_id") and not args.force:
            print(
                f"[learning_loop] request {audit['request_id']} already processed. "
                f"Pass --force to override."
            )
            if args.claude_dir:
                try:
                    save_to_claude_memory(settings, audit, args.claude_dir)
                except Exception as exc:
                    print(f"[learning_loop] Memory save failed (non-fatal): {exc}")
            return

        risk_score = audit.get("learning_flags", {}).get("risk_score", 1)
        skills_dir = Path.home() / ".claude" / "skills"
        changes = 0
        changes += update_skills(settings, audit)
        changes += update_mcp(settings, audit)
        changes += update_agent_stats(settings, audit)
        changes += check_pattern_hooks(settings, audit)
        changes += promote_skills_to_files(settings, skills_dir)
        changes += check_template_candidates(settings)
        changes += update_studio_wiki(audit, settings)
        changes += update_requirements_registry(args.requirements_registry, audit)
        changes += update_intent_registry(args.intent_registry, audit)

        settings["_meta"]["last_updated"] = datetime.now().strftime("%Y-%m-%d")
        settings["_meta"]["last_request_id"] = audit["request_id"]
        settings["_meta"]["last_processed_audit_log"] = audit["request_id"]
        settings["_meta"]["total_requests_processed"] = (
            settings["_meta"].get("total_requests_processed", 0) + 1
        )

        save_settings(settings, args.settings)
        print(f"[learning_loop] {changes} changes. Risk score: {risk_score}")

    if args.claude_dir:
        try:
            save_to_claude_memory(settings, audit, args.claude_dir)
        except Exception as exc:
            print(f"[learning_loop] Memory save failed (non-fatal): {exc}")

    if args.no_commit:
        print("[learning_loop] --no-commit set — skipping git commit.")
    elif risk_score < 3:
        commit_changes(args.settings, args.audit_dir, audit["request_id"])
    else:
        print(
            f"[learning_loop] Risk score {risk_score} >= 3. "
            + fmt(b("ui_strings.approval_pending_message"))
        )


if __name__ == "__main__":
    main()
