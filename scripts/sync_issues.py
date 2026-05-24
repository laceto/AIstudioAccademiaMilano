"""
sync_issues.py — Sync CLAUDE.md Open Issues ↔ GitHub Issues

Parses the Open Issues table from CLAUDE.md and:
  - Creates a GitHub Issue for every OPEN entry not yet tracked
  - Closes GitHub Issues whose CLAUDE.md status is DELIVERED
  - Idempotent: searches existing issues by ISS-NNN prefix before creating

Usage:
    python scripts/sync_issues.py           # dry run — shows what would change
    python scripts/sync_issues.py --apply   # apply changes via gh CLI
"""

import argparse
import json
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).parent.parent
CLAUDE_MD = ROOT / "CLAUDE.md"

PRIORITY_COLORS = {
    "P0": "B60205",
    "P1": "D93F0B",
    "P2": "FBCA04",
    "P3": "0E8A16",
}

ISSUE_BODY_TEMPLATE = """
**Tracked in:** `CLAUDE.md` → Open Issues

**Priority:** {priority}

**Context:** This issue is part of the AI Studio Accademia Milano operational backlog.
See `CLAUDE.md` for the full issue list and dependencies.
""".strip()


def parse_issues() -> list[dict]:
    """Parse Open Issues table from CLAUDE.md."""
    text = CLAUDE_MD.read_text(encoding="utf-8")
    # Find the Open Issues section
    match = re.search(r"## Open Issues\s*\n(.*?)(?=\n## |\Z)", text, re.DOTALL)
    if not match:
        print("ERROR: Could not find '## Open Issues' section in CLAUDE.md")
        sys.exit(1)

    issues = []
    for line in match.group(1).splitlines():
        # Match table rows: | ISS-NNN | Px | Title | STATUS |
        m = re.match(
            r"\|\s*(ISS-\d+)\s*\|\s*(P\d)\s*\|\s*(.+?)\s*\|\s*(OPEN|DELIVERED|CLOSED)\s*\|",
            line,
        )
        if m:
            issue_id, priority, title, status = m.groups()
            # Strip backtick-wrapped code in title for cleaner GH title
            clean_title = re.sub(r"`([^`]+)`", r"\1", title).strip()
            issues.append({
                "id": issue_id,
                "priority": priority,
                "title": clean_title,
                "raw_title": title.strip(),
                "status": status,
            })
    return issues


def gh(*args) -> str:
    """Run a gh CLI command and return stdout."""
    result = subprocess.run(
        ["gh", *args],
        capture_output=True,
        text=True,
        cwd=ROOT,
    )
    if result.returncode != 0:
        raise RuntimeError(f"gh {' '.join(args)} failed:\n{result.stderr}")
    return result.stdout.strip()


def get_existing_issues() -> dict[str, dict]:
    """Return {ISS-NNN: {number, state}} for all issues matching our naming pattern.
    Prefers OPEN issues over closed when duplicates exist (same ISS-NNN, multiple states).
    """
    raw = gh("issue", "list", "--json", "number,title,state", "--limit", "200", "--state", "all")
    all_issues = json.loads(raw)
    result: dict[str, dict] = {}
    for issue in all_issues:
        m = re.match(r"(ISS-\d+)", issue["title"])
        if m:
            iss_id = m.group(1)
            existing = result.get(iss_id)
            # Prefer OPEN over closed; keep highest issue number on tie
            if existing is None:
                result[iss_id] = {"number": issue["number"], "state": issue["state"]}
            elif issue["state"] == "OPEN" and existing["state"] != "OPEN":
                result[iss_id] = {"number": issue["number"], "state": issue["state"]}
    return result


def ensure_label(priority: str, apply: bool) -> None:
    """Create priority label if missing."""
    color = PRIORITY_COLORS.get(priority, "ededed")
    if apply:
        subprocess.run(
            ["gh", "label", "create", priority,
             "--color", color,
             "--description", f"Priority {priority}",
             "--force"],
            capture_output=True,
            cwd=ROOT,
        )


def main() -> None:
    parser = argparse.ArgumentParser(description="Sync CLAUDE.md issues → GitHub Issues")
    parser.add_argument("--apply", action="store_true", help="Apply changes (default: dry run)")
    args = parser.parse_args()

    issues = parse_issues()
    existing = get_existing_issues()

    print(f"Found {len(issues)} issues in CLAUDE.md")
    print(f"Found {len(existing)} matching GitHub Issues\n")

    created = closed = skipped = 0

    for issue in issues:
        iss_id   = issue["id"]
        priority = issue["priority"]
        # Strip non-ASCII characters (arrows etc.) for Windows console safety
        title    = issue["title"].encode("ascii", errors="replace").decode("ascii")
        status   = issue["status"]
        gh_title = f"{iss_id} [{priority}] {issue['title']}"  # full Unicode for GH
        display  = f"{iss_id} [{priority}] {title}"           # ASCII-safe for console

        if iss_id in existing:
            gh_state = existing[iss_id]["state"]
            gh_num   = existing[iss_id]["number"]

            if status == "DELIVERED" and gh_state == "OPEN":
                print(f"  CLOSE  #{gh_num}  {display}")
                if args.apply:
                    gh("issue", "close", str(gh_num), "--comment", "Delivered — closing.")
                closed += 1
            elif status == "OPEN" and gh_state == "CLOSED":
                print(f"  REOPEN #{gh_num}  {display}")
                if args.apply:
                    gh("issue", "reopen", str(gh_num))
                created += 1
            else:
                print(f"  OK     #{gh_num}  {display}  [{gh_state}]")
                skipped += 1
        else:
            if status == "OPEN":
                print(f"  CREATE          {display}")
                if args.apply:
                    ensure_label(priority, apply=True)
                    body = ISSUE_BODY_TEMPLATE.format(priority=priority)
                    gh("issue", "create",
                       "--title", gh_title,
                       "--body", body,
                       "--label", priority)
                created += 1
            else:
                print(f"  SKIP   (delivered, no GH issue)  {display}")
                skipped += 1

    print(f"\n{'Applied' if args.apply else 'Dry run'}:")
    print(f"  {created} to create/reopen  |  {closed} to close  |  {skipped} unchanged")
    if not args.apply:
        print("\nRun with --apply to execute.")


if __name__ == "__main__":
    main()
