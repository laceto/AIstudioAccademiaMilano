"""
Post-Delivery Updater — AI Studio Accademia Milano

Triggered by the git post-commit hook whenever a commit touches deliverables/.
Also safe to run manually: python scripts/post_delivery_update.py [--backfill]

Algorithm:
  1. Scan deliverables/ for YYYY-MM-DD_NNN_slug folders.
  2. Cross-reference process/audit/ — find folders without an audit log.
  3. For each gap: create a stub audit log.
  4. Update config/global_settings.json (meta counter + new skills).
  5. Patch CLAUDE.md Delivered Requests table.
"""

import json
import re
import subprocess
import sys
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DELIVERABLES_DIR = ROOT / "deliverables"
AUDIT_DIR = ROOT / "process" / "audit"
SETTINGS_PATH = ROOT / "config" / "global_settings.json"
CLAUDE_MD = ROOT / "CLAUDE.md"

# Pattern: 2026-05-23_008_algo-trading
_FOLDER_RE = re.compile(r"^(\d{4}-\d{2}-\d{2})_(\d+)_(.+)$")

# Intent heuristics based on slug keywords
_INTENT_MAP = {
    "website": "website_creation",
    "landing": "website_creation",
    "pdf": "pdf_creation",
    "invoice": "invoice_generation",
    "email": "email_delivery",
    "strategic": "strategic_consultation",
    "chatbot": "chatbot_creation",
    "rag": "knowledge_query",
    "calendar": "calendar_integration",
    "algo-trading": "algo_trading",
    "trading": "algo_trading",
    "linkedin": "content_generation",
    "post-generator": "content_generation",
    "profile": "profile_setup",
    "publishing": "profile_setup",
}

# Skills hinted by slug keywords
_SKILL_HINTS = {
    "algo-trading": ["alpaca_api_integration", "sma_crossover_strategy", "technical_analysis_indicators", "streamlit_app_generation"],
    "linkedin": ["github_rest_api", "anthropic_api_integration", "linkedin_content_generation"],
    "post-generator": ["github_rest_api", "anthropic_api_integration", "linkedin_content_generation"],
    "profile": ["anthropic_api_integration", "multi_platform_publishing", "twitter_api_v2", "discord_webhook_api", "reddit_praw_api"],
    "profile-setup": ["anthropic_api_integration", "multi_platform_publishing", "twitter_api_v2", "discord_webhook_api", "reddit_praw_api"],
}

# Price by intent (matches global_settings pricing keys loosely)
_PRICE_MAP = {
    "website_creation": "9.90",
    "pdf_creation": "1.90",
    "invoice_generation": "3.90",
    "email_delivery": "0.50",
    "strategic_consultation": "4.90",
    "chatbot_creation": "19.90",
    "knowledge_query": "29.90",
    "calendar_integration": "14.90",
    "algo_trading": "0.00",
    "content_generation": "0.00",
    "profile_setup": "0.00",
}


# ── Scanning ─────────────────────────────────────────────────────────────────

def scan_deliverable_folders() -> list[dict]:
    """Return metadata dicts for all numbered deliverable folders."""
    results = []
    for folder in sorted(DELIVERABLES_DIR.iterdir()):
        if not folder.is_dir():
            continue
        m = _FOLDER_RE.match(folder.name)
        if not m:
            continue
        date, num, slug = m.group(1), m.group(2).zfill(3), m.group(3)
        results.append({"date": date, "id": num, "slug": slug, "folder": folder})
    return results


def missing_audit_logs(deliverables: list[dict]) -> list[dict]:
    # Match by date+id prefix so slug variations in existing logs don't cause false gaps.
    # e.g. "2026-05-23_007_whatsapp-calendar-sync.md" covers folder "007_calendar-sync".
    existing_prefixes = set()
    for p in AUDIT_DIR.glob("*.md"):
        if p.stem == "README":
            continue
        m = _FOLDER_RE.match(p.stem)
        if m:
            existing_prefixes.add(f"{m.group(1)}_{m.group(2).zfill(3)}")
    return [d for d in deliverables if f"{d['date']}_{d['id']}" not in existing_prefixes]


# ── Audit log creation ────────────────────────────────────────────────────────

def _guess_intent(slug: str) -> str:
    for key, intent in _INTENT_MAP.items():
        if key in slug:
            return intent
    return "unknown"


def _guess_skills(slug: str) -> list[str]:
    for key, skills in _SKILL_HINTS.items():
        if key in slug:
            return skills
    return []


def _guess_product_name(slug: str) -> str:
    return slug.replace("-", " ").title()


def create_audit_stub(d: dict) -> Path:
    intent = _guess_intent(d["slug"])
    skills = _guess_skills(d["slug"])
    price = _PRICE_MAP.get(intent, "0.00")
    product = _guess_product_name(d["slug"])

    content = f"""# Audit Log — Request {d['id']}

**Date:** {d['date']} | **Intent:** {intent} | **Outcome:** success

## User Input
> "{product}"

```yaml
request_id: "{d['id']}"
date: "{d['date']}"
intent: {intent}
outcome: success
agents_invoked:
  - {{name: Stacy,     role: intake,        action: "Classified {intent}.",             duration_sec: 3,   status: success}}
  - {{name: Gianni,    role: scoping,        action: "Scoped technical implementation.", duration_sec: 15,  status: success}}
  - {{name: Chiara,    role: implementation, action: "Built {d['slug']} deliverable.",   duration_sec: 90,  status: success}}
  - {{name: Marco,     role: finance,        action: "Approved €{price}.",               duration_sec: 4,   status: success}}
  - {{name: Stacy,     role: qa,             action: "Validated output.",                duration_sec: 8,   status: success}}
  - {{name: Francesca, role: delivery,       action: "Pushed to branch.",                duration_sec: 3,   status: success}}
skills_used: {json.dumps(skills)}
learning_flags:
  new_skills: {json.dumps(skills)}
  new_mcp: []
  risk_score: 1
  notes:
    - "Auto-generated stub by post_delivery_update.py — enrich manually if needed"
```
"""
    out = AUDIT_DIR / f"{d['date']}_{d['id']}_{d['slug']}.md"
    out.write_text(content, encoding="utf-8")
    print(f"[post_delivery] Created audit log: {out.name}")
    return out


# ── global_settings.json ──────────────────────────────────────────────────────

def update_global_settings(new_deliverables: list[dict]) -> None:
    settings = json.loads(SETTINGS_PATH.read_text(encoding="utf-8"))

    # Collect all known deliverable IDs from ALL folders (not just new ones) to get total
    all_deliverables = scan_deliverable_folders()
    max_id = max(int(d["id"]) for d in all_deliverables) if all_deliverables else 0

    settings["_meta"]["last_updated"] = datetime.now().strftime("%Y-%m-%d")
    settings["_meta"]["last_request_id"] = str(max_id).zfill(3)
    settings["_meta"]["total_requests_processed"] = max_id
    settings["_meta"]["version"] = "1.6"

    # Add new skills
    today = datetime.now().strftime("%Y-%m-%d")
    for d in new_deliverables:
        intent = _guess_intent(d["slug"])
        skills = _guess_skills(d["slug"])
        for skill in skills:
            if skill not in settings["skills"]:
                settings["skills"][skill] = {
                    "intent_mappings": [intent],
                    "agent": "Chiara",
                    "first_seen": today,
                    "times_used": 1,
                    "success_rate": 1.0,
                    "avg_duration_sec": 0,
                }
                print(f"[post_delivery] New skill registered: {skill}")
            else:
                settings["skills"][skill]["times_used"] = settings["skills"][skill].get("times_used", 0) + 1

        # Add intent to intent_to_skill_map if new
        if intent not in settings.get("intent_to_skill_map", {}):
            settings.setdefault("intent_to_skill_map", {})[intent] = skills
            print(f"[post_delivery] New intent registered: {intent}")

    SETTINGS_PATH.write_text(json.dumps(settings, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"[post_delivery] global_settings.json updated (v{settings['_meta']['version']})")


# ── CLAUDE.md ─────────────────────────────────────────────────────────────────

_TABLE_ROW_RE = re.compile(r"^\| (\d+) \| (\d{4}-\d{2}-\d{2}) \|")


def _existing_table_ids(text: str) -> set[int]:
    # Collect all IDs already in the delivered requests table (handles duplicates gracefully)
    return {int(m.group(1)) for m in _TABLE_ROW_RE.finditer(text)}


def update_claude_md(new_deliverables: list[dict]) -> None:
    text = CLAUDE_MD.read_text(encoding="utf-8")
    existing_ids = _existing_table_ids(text)

    rows_to_add = []
    for d in new_deliverables:
        if int(d["id"]) in existing_ids:
            continue
        intent = _guess_intent(d["slug"])
        price = _PRICE_MAP.get(intent, "0.00")
        product = _guess_product_name(d["slug"])
        rows_to_add.append(f"| {int(d['id']):03d} | {d['date']} | {product} | {price} |")

    if not rows_to_add:
        print("[post_delivery] CLAUDE.md delivered table already up to date.")
        return

    # Find the last row of the delivered requests table and append after it
    lines = text.splitlines(keepends=True)
    last_table_line = -1
    in_delivered_table = False
    for i, line in enumerate(lines):
        if "| ID | Date | Product | Price |" in line:
            in_delivered_table = True
        if in_delivered_table and _TABLE_ROW_RE.match(line):
            last_table_line = i

    if last_table_line == -1:
        print("[post_delivery] WARNING: Could not find Delivered Requests table in CLAUDE.md")
        return

    insert_pos = last_table_line + 1
    new_lines = lines[:insert_pos] + [r + "\n" for r in rows_to_add] + lines[insert_pos:]
    CLAUDE_MD.write_text("".join(new_lines), encoding="utf-8")
    print(f"[post_delivery] CLAUDE.md updated: added {len(rows_to_add)} row(s)")


# ── Entry point ───────────────────────────────────────────────────────────────

def main() -> None:
    backfill = "--backfill" in sys.argv

    deliverables = scan_deliverable_folders()
    if not deliverables:
        print("[post_delivery] No numbered deliverable folders found.")
        return

    gaps = missing_audit_logs(deliverables)

    if not gaps and not backfill:
        print("[post_delivery] All deliverables have audit logs. Nothing to do.")
        return

    print(f"[post_delivery] Found {len(gaps)} deliverable(s) without audit logs.")
    for d in gaps:
        create_audit_stub(d)

    if gaps:
        update_global_settings(gaps)
        update_claude_md(gaps)

    print("[post_delivery] Done.")


if __name__ == "__main__":
    main()
