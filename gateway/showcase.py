"""
gateway/showcase.py — Auto-publish a product gallery from audit logs.

Reads `process/audit/*.md`, extracts the YAML frontmatter, and emits a list of
ShowcaseCard objects for the cards FastAPI serves at `/`.

Filter rules:
  - outcome, if present, must not start with "fail" (drops "failed", "failure";
    accepts missing outcome since newer logs encode pass/fail via qa_result
    and per-agent status instead of a top-level field)
  - product_type must be in config/global_settings.json `pricing` with a
    non-null, non-zero price (drops internal_infra_build, kiosk_deploy_pilot,
    unknown_product)
  - the YAML block must parse

Cards carry the price and a derived title so the gallery template stays dumb.
"""

import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml

_REPO_ROOT = Path(__file__).resolve().parent.parent
_DEFAULT_AUDIT_DIR = _REPO_ROOT / "process" / "audit"
_PRICING_PATH = _REPO_ROOT / "config" / "global_settings.json"

_YAML_BLOCK = re.compile(r"```yaml\s*\n(.*?)\n```", re.DOTALL)


@dataclass(frozen=True)
class ShowcaseCard:
    request_id: str
    date: str
    intent: str
    product_type: str
    price_eur: float
    title: str
    live_url: str | None = None  # set in audit YAML or via <PRODUCT_TYPE_upper>_URL env var


def _load_pricing(path: Path = _PRICING_PATH) -> dict[str, float]:
    """Parse the pricing block from global_settings.json into a {product: euros} map.

    Strings like "€9.90" → 9.90; null / "€0.00" entries are dropped.
    """
    raw = json.loads(path.read_text(encoding="utf-8")).get("pricing", {})
    out: dict[str, float] = {}
    for key, value in raw.items():
        if value is None:
            continue
        cleaned = str(value).replace("€", "").replace(",", ".").strip()
        try:
            euros = float(cleaned)
        except ValueError:
            continue
        if euros > 0:
            out[key] = euros
    return out


def parse_audit(path: Path) -> dict[str, Any] | None:
    """Extract the YAML frontmatter block from an audit-log Markdown file."""
    try:
        text = path.read_text(encoding="utf-8")
    except OSError:
        return None
    m = _YAML_BLOCK.search(text)
    if not m:
        return None
    try:
        data = yaml.safe_load(m.group(1))
    except yaml.YAMLError:
        return None
    if not isinstance(data, dict):
        return None
    return data


_UPPERCASE_TOKENS = {"pdf", "rag", "ai", "ui", "api"}


def _humanize(product_type: str) -> str:
    words = []
    for token in product_type.replace("_", " ").split():
        words.append(token.upper() if token.lower() in _UPPERCASE_TOKENS else token.title())
    return " ".join(words)


def _build_card(audit: dict[str, Any], pricing: dict[str, float]) -> ShowcaseCard | None:
    import os
    outcome = str(audit.get("outcome", "")).strip().lower()
    if outcome.startswith("fail"):
        return None
    product_type = str(audit.get("product_type", "")).strip()
    price = pricing.get(product_type)
    if price is None:
        return None
    request_id = str(audit.get("request_id", "")).strip()
    date = str(audit.get("date", "")).strip()
    intent = str(audit.get("intent", "")).strip()
    if not (request_id and date and product_type):
        return None
    # live_url: from audit YAML, then env var <PRODUCT_TYPE_UPPER>_URL, then None
    live_url = audit.get("live_url") or os.environ.get(
        product_type.upper() + "_URL"
    ) or None
    return ShowcaseCard(
        request_id=request_id,
        date=date,
        intent=intent,
        product_type=product_type,
        price_eur=price,
        title=_humanize(product_type),
        live_url=live_url if live_url and str(live_url).lower() not in ("null", "none", "") else None,
    )


def load_cards(audit_dir: Path = _DEFAULT_AUDIT_DIR) -> list[ShowcaseCard]:
    """Walk audit_dir/*.md, return showcase-eligible cards sorted newest first."""
    pricing = _load_pricing()
    cards: list[ShowcaseCard] = []
    seen_ids: set[str] = set()
    for path in sorted(audit_dir.glob("*.md")):
        audit = parse_audit(path)
        if not audit:
            continue
        card = _build_card(audit, pricing)
        if not card:
            continue
        if card.request_id in seen_ids:
            continue  # collision (e.g. multiple _011_ logs) — first one wins
        seen_ids.add(card.request_id)
        cards.append(card)
    cards.sort(key=lambda c: (c.date, c.request_id), reverse=True)
    return cards
