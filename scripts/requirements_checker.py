#!/usr/bin/env python3
"""
Requirements checker — called by Gianni before scoping starts.

Usage:
    python requirements_checker.py <product_type>
    python requirements_checker.py algo_trading
    python requirements_checker.py --list
"""

import sys
import yaml
from pathlib import Path

REGISTRY_PATH = Path(__file__).parent.parent / "config" / "requirements_registry.yaml"


def _load_registry() -> dict:
    with open(REGISTRY_PATH) as f:
        return yaml.safe_load(f)


def list_product_types() -> list[str]:
    return list(_load_registry()["products"].keys())


def check_requirements(product_type: str) -> dict:
    """Return the requirements spec for a product type, or raise ValueError."""
    registry = _load_registry()
    products = registry["products"]
    if product_type not in products:
        known = ", ".join(products.keys())
        raise ValueError(
            f"Unknown product type: '{product_type}'. Known types: {known}"
        )
    spec = products[product_type]
    pricing = registry.get("pricing", {})
    return {
        "product_type": product_type,
        "label": spec.get("label", product_type),
        "price": pricing.get(product_type),
        "required": spec.get("required", []),
        "optional": spec.get("optional", []),
        "manual_only": spec.get("manual_only", []),
    }


def format_requirements_manifest(product_type: str) -> str:
    """Return a human-readable Requirements Manifest as Markdown."""
    req = check_requirements(product_type)
    lines = []

    price_str = (
        f"€{req['price']:.2f}" if req["price"] is not None else "⚠️ Price TBD — Luigi must approve"
    )

    lines.append(f"## Requirements Manifest: {req['label']}")
    lines.append(f"**Price:** {price_str}  |  **Product type:** `{product_type}`")
    lines.append("")

    if req["required"]:
        lines.append("### ✅ Required — you need ALL of these before we can start")
        lines.append("")
        lines.append("| # | What | Type | How to get it |")
        lines.append("|---|------|------|---------------|")
        for i, item in enumerate(req["required"], 1):
            signup = item.get("signup_url") or item.get("setup_url") or "—"
            if signup != "—":
                signup = f"[Sign up / Setup]({signup})"
            lines.append(
                f"| {i} | **{item['name']}** | `{item['type']}` | {signup} |"
            )
        lines.append("")
        lines.append("**Notes:**")
        for item in req["required"]:
            if item.get("notes"):
                lines.append(f"- **{item['name']}**: {item['notes']}")
        lines.append("")

    if req["optional"]:
        lines.append("### ⚙️ Optional — enables extra features")
        lines.append("")
        lines.append("| # | What | Type | Notes |")
        lines.append("|---|------|------|-------|")
        for i, item in enumerate(req["optional"], 1):
            signup = item.get("signup_url") or item.get("setup_url") or ""
            name = item["name"]
            if signup:
                name = f"[{name}]({signup})"
            lines.append(
                f"| {i} | {name} | `{item['type']}` | {item.get('notes', '')} |"
            )
        lines.append("")

    if req["manual_only"]:
        lines.append("### 🖐️ Manual only — no API available, must do by hand")
        lines.append("")
        for item in req["manual_only"]:
            lines.append(f"- **{item['name']}**: {item.get('notes', '')}")
        lines.append("")

    lines.append("---")
    lines.append(
        "_Reply **GO** when you have everything above, or **SKIP** to defer optional items. "
        "Implementation starts only after you confirm._"
    )

    return "\n".join(lines)


def main():
    if len(sys.argv) < 2 or sys.argv[1] in ("-h", "--help"):
        print(__doc__)
        sys.exit(0)

    if sys.argv[1] == "--list":
        registry = _load_registry()
        products = registry["products"]
        pricing = registry.get("pricing", {})
        print("Available product types:\n")
        for key, spec in products.items():
            price = pricing.get(key)
            price_str = f"€{price:.2f}" if price else "TBD"
            print(f"  {key:<30} {spec.get('label', '')} ({price_str})")
        sys.exit(0)

    product_type = sys.argv[1]
    try:
        manifest = format_requirements_manifest(product_type)
        print(manifest)
    except ValueError as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
