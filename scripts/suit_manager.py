"""
Suit manager — loads, validates, and resolves configuration for any suit instance.

Usage:
    python scripts/suit_manager.py list
    python scripts/suit_manager.py show S001
    python scripts/suit_manager.py create S002 --name "Acme AI Studio" --owner "Jane Doe" --email "jane@acme.com"
    python scripts/suit_manager.py env S002       # emit shell export block for env_prefix wiring
"""
import argparse
import copy
import os
import sys
from datetime import date
from pathlib import Path

import yaml

REPO_ROOT  = Path(__file__).resolve().parent.parent
SUITS_DIR  = REPO_ROOT / "config" / "suits"
SCHEMA     = SUITS_DIR / "suit_schema.yaml"
SETTINGS   = REPO_ROOT / "config" / "global_settings.json"

# ── helpers ───────────────────────────────────────────────────────────────────

def load_yaml(path: Path) -> dict:
    with open(path) as f:
        return yaml.safe_load(f) or {}


def list_suits() -> list[dict]:
    suits = []
    for f in sorted(SUITS_DIR.glob("S*.yaml")):
        if f.name == "suit_schema.yaml":
            continue
        d = load_yaml(f)
        suits.append({
            "suit_id":   d.get("suit_id", "?"),
            "suit_name": d.get("suit_name", "?"),
            "owner":     d.get("owner_name", "?"),
            "file":      f.name,
        })
    return suits


def load_suit(suit_id: str) -> dict:
    # merge schema defaults <- suit file
    schema  = load_yaml(SCHEMA)
    matches = list(SUITS_DIR.glob(f"{suit_id}_*.yaml"))
    if not matches:
        raise FileNotFoundError(f"No config file for suit '{suit_id}' in {SUITS_DIR}")
    suit_raw = load_yaml(matches[0])
    merged   = deep_merge(schema, suit_raw)
    return merged


def deep_merge(base: dict, override: dict) -> dict:
    result = copy.deepcopy(base)
    for k, v in override.items():
        if isinstance(v, dict) and isinstance(result.get(k), dict):
            result[k] = deep_merge(result[k], v)
        else:
            result[k] = v
    return result


def create_suit(suit_id: str, name: str, owner: str, email: str) -> Path:
    existing = list(SUITS_DIR.glob(f"{suit_id}_*.yaml"))
    if existing:
        raise ValueError(f"Suit {suit_id} already exists: {existing[0]}")
    slug = name.lower().replace(" ", "-").replace("/", "-")[:30]
    out_path = SUITS_DIR / f"{suit_id}_{slug}.yaml"
    config = {
        "suit_id":     suit_id,
        "suit_name":   name,
        "owner_name":  owner,
        "owner_email": email,
        "founded":     str(date.today()),
        "locale":      "en_US",
        "currency":    "EUR",
        "agent_personas": {},        # inherits canonical names
        "pricing_overrides": {},     # inherits global_settings.json pricing
        "env_prefix":  suit_id,      # e.g. S002_OPENAI_API_KEY
        "hosting": {
            "static": "vercel",
            "apps":   "streamlit-cloud",
            "repo_org": slug,
        },
        "audit_dir": "process/audit",
        "learning_loop": {
            "claude_dir": "$HOME/.claude",
            "auto_commit_risk_threshold": 3,
        },
        "license": {
            "origin_suit": "S001",
            "issued_date": str(date.today()),
            "licensed_to": owner,
        },
    }
    out_path.write_text(yaml.dump(config, default_flow_style=False, allow_unicode=True))
    return out_path


def emit_env_block(suit: dict) -> str:
    prefix = suit.get("env_prefix") or suit["suit_id"]
    vars_needed = [
        "OPENAI_API_KEY", "ANTHROPIC_API_KEY", "GITHUB_TOKEN",
        "STRIPE_SECRET_KEY", "TWILIO_ACCOUNT_SID", "TWILIO_AUTH_TOKEN",
        "TELEGRAM_BOT_TOKEN", "VERCEL_TOKEN", "CLOUDFLARE_API_TOKEN",
    ]
    lines = [f"# Env vars for suit {suit['suit_id']} — {suit['suit_name']}"]
    for v in vars_needed:
        lines.append(f"export {prefix}_{v}=''  # fill in")
    return "\n".join(lines)


# ── CLI ───────────────────────────────────────────────────────────────────────

def cmd_list(_args):
    suits = list_suits()
    print(f"{'SUIT_ID':<8} {'NAME':<35} {'OWNER':<25} FILE")
    print("-" * 85)
    for s in suits:
        print(f"{s['suit_id']:<8} {s['suit_name']:<35} {s['owner']:<25} {s['file']}")


def cmd_show(args):
    suit = load_suit(args.suit_id)
    print(yaml.dump(suit, default_flow_style=False, allow_unicode=True))


def cmd_create(args):
    path = create_suit(args.suit_id, args.name, args.owner, args.email)
    print(f"Created: {path}")


def cmd_env(args):
    suit = load_suit(args.suit_id)
    print(emit_env_block(suit))


def main():
    parser = argparse.ArgumentParser(description="Suit manager")
    sub = parser.add_subparsers(dest="cmd", required=True)

    sub.add_parser("list")

    p_show = sub.add_parser("show")
    p_show.add_argument("suit_id")

    p_create = sub.add_parser("create")
    p_create.add_argument("suit_id")
    p_create.add_argument("--name",  required=True)
    p_create.add_argument("--owner", required=True)
    p_create.add_argument("--email", required=True)

    p_env = sub.add_parser("env")
    p_env.add_argument("suit_id")

    args = parser.parse_args()
    {"list": cmd_list, "show": cmd_show, "create": cmd_create, "env": cmd_env}[args.cmd](args)


if __name__ == "__main__":
    main()
