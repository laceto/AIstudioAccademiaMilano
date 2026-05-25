"""
Delta Collector — AI Studio Accademia Milano.

Runs at session end (Stop hook) to produce process/deltas/YYYY-MM-DD.json.
Merges two sources:
  1. git log  — file-level changes (what changed)
  2. audit logs — agent/skill/hook events (what agents did and why)

Retention: deletes delta files older than 90 days.

Usage:
    python scripts/delta_collector.py --date today --audit-dir process/audit --output process/deltas
"""

import argparse
import json
import subprocess
from datetime import date, datetime, timedelta
from pathlib import Path

# Import shared audit parse logic — avoids duplication
from scripts.learning_loop import parse_audit_log, _AUDIT_LOG_RE

_FILE_CATEGORIES = {
    ".py":   "py",
    ".md":   "md",
    ".json": "json",
    ".yaml": "yaml",
    ".yml":  "yaml",
}

_KNOWN_AGENTS = ["Stacy", "Gianni", "Chiara", "Marco", "Francesca", "Valentina", "Lorenzo"]


def _ext_category(path_str: str) -> str:
    ext = Path(path_str).suffix.lower()
    return _FILE_CATEGORIES.get(ext, "other")


def _zero_categories() -> dict:
    ext_zero = {"py": 0, "md": 0, "json": 0, "yaml": 0, "other": 0}
    return {
        "file_edits":        ext_zero.copy(),
        "file_creates":      ext_zero.copy(),
        "file_deletes":      ext_zero.copy(),
        "agent_invocations": {a: 0 for a in _KNOWN_AGENTS},
        "skills_used":       {},
        "hooks_fired":       {},
        "deploys":           0,
        "tests_run":         0,
    }


def collect_git_delta(since_date: str) -> dict:
    """
    Parse git log for commits since since_date.
    Uses two separate calls to avoid --stat + --pretty=format mixing issues.
    """
    categories = _zero_categories()
    commit_count = 0

    # Call 1: commit hashes for the day
    try:
        hash_out = subprocess.check_output(
            ["git", "log", f"--since={since_date} 00:00:00",
             f"--until={since_date} 23:59:59",
             "--pretty=format:%H"],
            text=True, stderr=subprocess.DEVNULL,
        ).strip()
    except subprocess.CalledProcessError:
        return categories

    hashes = [h for h in hash_out.splitlines() if h]
    commit_count = len(hashes)

    # Call 2: file-level stat per commit
    for h in hashes:
        try:
            stat_out = subprocess.check_output(
                ["git", "show", "--stat", "--name-status", "--format=", h],
                text=True, stderr=subprocess.DEVNULL,
            ).strip()
        except subprocess.CalledProcessError:
            continue

        for line in stat_out.splitlines():
            parts = line.split("\t")
            if len(parts) < 2:
                continue
            status, *rest = parts
            filepath = rest[-1] if rest else ""
            cat = _ext_category(filepath)
            if status.startswith("M"):
                categories["file_edits"][cat] = categories["file_edits"].get(cat, 0) + 1
            elif status.startswith("A"):
                categories["file_creates"][cat] = categories["file_creates"].get(cat, 0) + 1
            elif status.startswith("D"):
                categories["file_deletes"][cat] = categories["file_deletes"].get(cat, 0) + 1

    if "deploy" in "".join(
        subprocess.check_output(
            ["git", "log", f"--since={since_date} 00:00:00",
             f"--until={since_date} 23:59:59",
             "--pretty=format:%s"],
            text=True, stderr=subprocess.DEVNULL,
        ).lower().splitlines()
    ):
        categories["deploys"] += 1

    return categories


def collect_audit_delta(audit_dir: str, target_date: str) -> tuple[dict, list, dict]:
    """
    Parse audit logs created on target_date.
    Returns (categories_patch, request_ids, outcomes).
    """
    categories = _zero_categories()
    request_ids = []
    outcomes = {"success": 0, "failure": 0}

    audit_path = Path(audit_dir)
    for log_file in sorted(audit_path.glob("*.md")):
        if not _AUDIT_LOG_RE.match(log_file.name):
            continue
        # Check date prefix (YYYY-MM-DD_NNN_slug.md)
        if not log_file.name.startswith(target_date):
            continue
        try:
            audit = parse_audit_log(log_file)
        except Exception:
            continue

        req_id = audit.get("request_id")
        if req_id:
            request_ids.append(str(req_id))

        outcome = audit.get("outcome", "unknown")
        if outcome == "success":
            outcomes["success"] += 1
        else:
            outcomes["failure"] += 1

        for agent_entry in audit.get("agents_invoked", []) or []:
            name = agent_entry.get("name", "")
            if name in categories["agent_invocations"]:
                categories["agent_invocations"][name] += 1

        for skill in audit.get("skills_used", []) or []:
            categories["skills_used"][skill] = categories["skills_used"].get(skill, 0) + 1

        for hook in audit.get("hooks_fired", []) or []:
            categories["hooks_fired"][hook] = categories["hooks_fired"].get(hook, 0) + 1

        if audit.get("delivery", {}).get("confirmed"):
            categories["deploys"] += 1

    return categories, request_ids, outcomes


def _merge(git_cats: dict, audit_cats: dict) -> dict:
    merged = {}
    for key in git_cats:
        if isinstance(git_cats[key], dict):
            merged[key] = {}
            all_keys = set(git_cats[key]) | set(audit_cats.get(key, {}))
            for k in all_keys:
                merged[key][k] = git_cats[key].get(k, 0) + audit_cats.get(key, {}).get(k, 0)
        else:
            merged[key] = git_cats[key] + audit_cats.get(key, 0)
    return merged


def write_delta(delta: dict, output_dir: str) -> Path:
    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)
    target = out / f"{delta['date']}.json"
    target.write_text(json.dumps(delta, indent=2, ensure_ascii=False), encoding="utf-8")
    return target


def _purge_old_deltas(output_dir: str, max_days: int = 90) -> None:
    cutoff = date.today() - timedelta(days=max_days)
    for f in Path(output_dir).glob("*.json"):
        try:
            file_date = date.fromisoformat(f.stem)
            if file_date < cutoff:
                f.unlink()
                print(f"  [DeltaCollector] Purged old delta: {f.name}")
        except ValueError:
            pass


def main():
    parser = argparse.ArgumentParser(description="Collect daily codebase delta")
    parser.add_argument("--date", default="today",
                        help="Date to collect (YYYY-MM-DD or 'today')")
    parser.add_argument("--audit-dir", default="process/audit")
    parser.add_argument("--output", default="process/deltas")
    args = parser.parse_args()

    target_date = date.today().isoformat() if args.date == "today" else args.date

    print(f"[DeltaCollector] Collecting delta for {target_date}...")

    git_cats = collect_git_delta(target_date)
    audit_cats, request_ids, outcomes = collect_audit_delta(args.audit_dir, target_date)
    merged = _merge(git_cats, audit_cats)

    delta = {
        "date": target_date,
        "generated_at": datetime.utcnow().isoformat() + "Z",
        "categories": merged,
        "request_ids": sorted(set(request_ids)),
        "total_requests": len(set(request_ids)),
        "outcomes": outcomes,
    }

    out_path = write_delta(delta, args.output)
    print(f"  -> Written: {out_path}")
    print(f"  -> Requests: {delta['total_requests']} | Success: {outcomes['success']} | Failure: {outcomes['failure']}")

    _purge_old_deltas(args.output)


if __name__ == "__main__":
    main()
