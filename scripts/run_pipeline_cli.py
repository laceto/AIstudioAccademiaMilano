#!/usr/bin/env python3
"""
CLI entry point for the 6-agent pipeline.
Used by the GitHub Action and any shell caller.

Usage:
  python scripts/run_pipeline_cli.py --request "Build a chatbot" \
      [--user-name Luigi] [--user-email x@y.com] [--provider anthropic|openai]
"""
import argparse
import importlib.util
import json
import os
import sys
import types
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def _load_pipeline():
    """Load run_pipeline from the hyphenated deliverable directory."""
    pkg_dir = ROOT / "deliverables" / "2026-05-25_016_aistudio-langgraph"
    PKG = "studio_pipeline"

    # Create package namespace
    pkg = types.ModuleType(PKG)
    pkg.__path__ = [str(pkg_dir)]
    pkg.__package__ = PKG
    sys.modules[PKG] = pkg
    sys.path.insert(0, str(ROOT))  # for config.brand etc.

    # Register + execute submodules in dependency order
    for name in ("state", "llm_factory", "nodes", "graph"):
        fqn = f"{PKG}.{name}"
        spec = importlib.util.spec_from_file_location(
            fqn,
            pkg_dir / f"{name}.py",
            submodule_search_locations=[str(pkg_dir)],
        )
        mod = importlib.util.module_from_spec(spec)
        mod.__package__ = PKG
        sys.modules[fqn] = mod
        spec.loader.exec_module(mod)

    return sys.modules[f"{PKG}.graph"].run_pipeline


def _banner(text: str) -> None:
    width = 72
    print("=" * width)
    print(f"  {text}")
    print("=" * width)


def main() -> int:
    parser = argparse.ArgumentParser(description="AI Studio 6-Agent Pipeline")
    parser.add_argument("--request",    required=True,  help="The client request")
    parser.add_argument("--user-name",  default="Cliente")
    parser.add_argument("--user-email", default=None)
    parser.add_argument("--provider",   default="openai", choices=["anthropic", "openai"])
    args = parser.parse_args()

    _banner("AI Studio Accademia Milano — Pipeline Run")
    print(f"  Request  : {args.request}")
    print(f"  Client   : {args.user_name}")
    print(f"  Provider : {args.provider}")
    print()

    try:
        run_pipeline = _load_pipeline()
    except Exception as exc:
        print(f"[IMPORT ERROR] {exc}", file=sys.stderr)
        return 1

    config = {"configurable": {"provider": args.provider}}

    try:
        steps, final = run_pipeline(
            request=args.request,
            user_name=args.user_name,
            user_email=args.user_email,
            config=config,
        )
    except Exception as exc:
        print(f"[PIPELINE ERROR] {exc}", file=sys.stderr)
        return 1

    # ── Print each agent step ─────────────────────────────────────────────
    print(f"{'─' * 72}")
    print(f"  PIPELINE STEPS  ({len(steps)} events)")
    print(f"{'─' * 72}")
    for i, step in enumerate(steps, 1):
        print(f"  [{i:02d}] {step['content']}")
    print()

    if not final:
        print("[ERROR] No final state returned.", file=sys.stderr)
        return 1

    # ── Summary ───────────────────────────────────────────────────────────
    _banner("DELIVERY SUMMARY")
    delivery = final.get("delivery_result") or {}
    print(f"  Status        : {delivery.get('status', 'unknown')}")
    print(f"  Deliverable   : {delivery.get('deliverable_path', 'n/a')}")
    print(f"  Audit log     : {delivery.get('audit_log', 'n/a')}")
    print(f"  Git           : {delivery.get('git_status', 'n/a')}")
    print(f"  Email         : {delivery.get('email_status', 'n/a')}")
    print()
    print(f"  Invoice ID    : {final.get('invoice_id', 'n/a')}")
    print(f"  Price         : €{final.get('product_price', '0.00')}")
    print(f"  Product type  : {final.get('product_type', 'n/a')}")
    print(f"  QA passed     : {final.get('qa_passed', False)}")
    print(f"  Risk score    : {final.get('aggregate_risk_score', 0.0):.1f}/5")

    if final.get("escalate_to_luigi"):
        print()
        print(f"  ESCALATED     : {final.get('escalation_reason')}")

    print("=" * 72)

    # ── Write outputs for GitHub Actions ──────────────────────────────────
    summary = {
        "status":           delivery.get("status", "unknown"),
        "deliverable_path": delivery.get("deliverable_path"),
        "audit_log":        delivery.get("audit_log"),
        "invoice_id":       final.get("invoice_id"),
        "price_eur":        final.get("product_price"),
        "product_type":     final.get("product_type"),
        "git_status":       delivery.get("git_status"),
        "escalated":        bool(final.get("escalate_to_luigi")),
    }
    gho = os.getenv("GITHUB_OUTPUT")
    if gho:
        with open(gho, "a") as fh:
            fh.write(f"summary={json.dumps(summary)}\n")
            fh.write(f"status={summary['status']}\n")
            fh.write(f"deliverable_path={summary['deliverable_path'] or ''}\n")
            fh.write(f"price_eur={summary['price_eur'] or '0.00'}\n")
            fh.write(f"escalated={'true' if summary['escalated'] else 'false'}\n")

    return 0 if delivery.get("status") == "delivered" else 1


if __name__ == "__main__":
    sys.exit(main())
